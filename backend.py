import pyodbc
from dotenv import load_dotenv
import os

import pandas as pd
import numpy as np

# ---- Load app setting from config ----
from config_loader import load_config
config = load_config()
DEMO_MODE = config['demo_mode']

# ---- Database connection using .env variables ----

# Load environment variables
script_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path)

def get_db_connection():
    server = os.getenv("SQL_SERVER")
    database = os.getenv("SQL_DATABASE")
    username = os.getenv("SQL_USERNAME")
    password = os.getenv("SQL_PASSWORD")

    conn = pyodbc.connect(
        f'DRIVER=ODBC Driver 17 for SQL Server;'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'UID={username};'
        f'PWD={password};'
        # 'Encrypt=yes;'
    )
    return conn

# ---- Business Logic ----

# get tool data (min duration only)
def load_data(limit: int = 1000):
    if not DEMO_MODE:
        conn = get_db_connection()
        query = f'''
        SET NOCOUNT ON
        SET ANSI_WARNINGS OFF
        ;

        DECLARE @Plant INT=2100
        ------------------------------------------- ToolCounter ------------------------------------
        SELECT TL.ToolNoId,mmTool.ToolID mmToolID,mmTool.ToolingMaker,TN.MachineId,TN.IdentifyNo,TL.StartCounter,TL.CurrentCounter,TL.TotalCounter, TL.IsActiveTool,
        TL.StartDate, GetDate() CompletedDate,TN.ToolPieces,
        mmTool.ToolingStation,mmTool.ProductGroup,mmTool.ToolingClass,mmTool.ToolingMainCategory, mmTool.ToolingSubCategory, mmTool.SAPCode,
        ISNULL(mmTool.PresetCounter,0)PresetCounter
        INTO #ToolLife FROM ToolLife TL
        INNER JOIN (ToolNo TN INNER JOIN mmTool mmTool ON TN.mmToolID=mmTool.ID)
        ON TL.ToolNoId=TN.Id
        WHERE TN.MachineID LIKE 'MS%'
        AND TL.IsActiveTool=1
        ORDER BY MACHINEID,SAPCode DESC

        --SELECT TL.ToolNoId,mmTool.ToolID mmToolID,mmTool.ToolingMaker,TN.MachineId,TN.IdentifyNo,TL.StartCounter,TL.CurrentCounter,TL.TotalCounter, 0 IsActiveTool,
        --TL.StartDate, TL.CompletedDate,TN.ToolPieces,
        --mmTool.ToolingStation,mmTool.ProductGroup,mmTool.ToolingClass,mmTool.ToolingMainCategory, mmTool.ToolingSubCategory, mmTool.SAPCode,
        --ISNULL(mmTool.PresetCounter,0)PresetCounter
        --INTO #ToolLifeHist FROM ToolLifeHistory TL
        --INNER JOIN (ToolNo TN INNER JOIN mmTool mmTool ON TN.mmToolID=mmTool.ID)
        --ON TL.ToolNoId=TN.Id
        --WHERE TL.ToolNoId IN (SELECT ToolNoID FROM #ToolLife)
        --ORDER BY MACHINEID,SAPCode DESC

        --INSERT INTO #ToolLife SELECT * FROM #ToolLifeHist
        -- drop table #ToolLife,#ToolLifeHist

        ------------------------------------------- Material & Machine Information ------------------------------------
        SELECT Plant, MachineID, Dept, MaterialCode, MaterialDescription, MesCT
        INTO #Session  FROM [SPLOEE].[dbo].[Session]
        WHERE MachineID IN (SELECT DISTINCT MachineID FROM #ToolLife)
        AND SessionStatus='RUNNING' AND Plant=@Plant

        SELECT Plant,Dept,MachineID,MachineNo Location
        INTO #WCMachineID FROM [MDM].[dbo].[WorkCenterMachineID]
        WHERE MachineID IN (SELECT DISTINCT MachineID FROM #ToolLife)
        AND DelFlag=0 AND IsActive=1 AND Plant=@Plant

        ------------------------------------------- ToolLifeDetails In Group ------------------------------------
        SELECT MachineID,ToolNoID,ToolingMainCategory,ToolingSubCategory,ToolingStation,SUM(TotalCounter) TotalCounter,PresetCounter
        INTO #TL FROM #ToolLife
        GROUP BY MachineID,ToolNoID,ToolingMainCategory,ToolingSubCategory,ToolingStation,PresetCounter
        ORDER BY MachineID,ToolingMainCategory,ToolingStation

        SELECT #TL.*,(#TL.PresetCounter-#TL.TotalCounter) Balance, 
        #Session.MesCT,#Session.MaterialCode,#Session.MaterialDescription,
        #WCMachineID.Location,0 DurationMins
        INTO #ToolInfo FROM #TL
        LEFT OUTER JOIN #Session ON #TL.MachineID=#Session.MachineID
        LEFT OUTER JOIN #WCMachineID ON #TL.MachineID=#WCMachineID.MachineID

        ------------------------------------------- Revise ToolCounter (Muratec Data) 27/06/25 ------------------------------------
        UPDATE TI 
        SET 
            TI.PresetCounter = TC.ToolSetPoint,
            TI.Balance = TC.ToolBalance,
            TI.TotalCounter = TC.ToolQty
        FROM 
            #ToolInfo TI 
        INNER JOIN ToolCount TC ON 
            TI.MachineID = TC.MacID
            AND TI.ToolingMainCategory = TC.MainCategory
            AND TI.ToolingStation = TC.ToolStation

        UPDATE #ToolInfo SET Balance=0 WHERE Balance<0
        UPDATE #ToolInfo SET DurationMins=(Balance*MesCT)/60
        ------------------------------------------- ToolLife Summary ------------------------------------
        DECLARE @RowNum INT=1
        DECLARE @TotalRow INT
        SET @TotalRow = (SELECT COUNT(DISTINCT MachineID) from #ToolInfo)

        CREATE TABLE #ToolSummary (
        MachineID NVARCHAR(18),
        Location NVARCHAR(10),
        MaterialCode NVARCHAR(40),
        MaterialDesc NVARCHAR(40),
        ToolingStation INT,
        TotalCounter INT,
        PresetCounter INT,
        BalanceCounter INT,
        DurationMins INT,
        TechRequired BIT,
        MacLEDGreen BIT,
        MacLEDYellow BIT,
        MacLEDRed BIT,
        MacStatus INT
        )

        WHILE @RowNum <= @TotalRow
        BEGIN
            INSERT INTO #ToolSummary SELECT TOP 1 MachineID,Location,MaterialCode,MaterialDescription,
                ToolingStation,TotalCounter,PresetCounter,Balance,DurationMins,0,0,0,0,0 
            FROM #ToolInfo
            WHERE MachineID NOT IN (SELECT MachineID FROM #ToolSummary)
            ORDER BY DurationMins
            SET @RowNum= @RowNum+1
        END

        ------------------------------------------- Technical Request Information ------------------------------------
        DECLARE @ProdnShift INT
        DECLARE @PrevDay INT
        DECLARE @ProdnDate AS DATE

        SELECT TOP 1 @ProdnShift=Shift,@PrevDay=CAST(PreviousDay AS INT) FROM mdm.dbo.TSHIFT
        WHERE Plant=@Plant AND ISNULL(DelFlag,0)=0 AND CAST(getdate() AS TIME)
        BETWEEN StartTime AND EndTime
        SET @ProdnDate = DATEADD(d,-@PrevDay,CAST(getdate() AS DATE))

        SELECT DT.ID,Kep.MacID,DT.TechRequired
        INTO #DT FROM [SPLOEE].[dbo].[OEEDownTime] DT
        LEFT OUTER JOIN [SPLOEE].[dbo].[OEEOUTPUTKEP] Kep ON DT.ID=Kep.ID
        WHERE Kep.ProdnDate=@ProdnDate AND Kep.ProdnShift=@ProdnShift
        AND DT.TechRequired=1
        AND Kep.MacID IN (SELECT MachineID FROM #ToolSummary)
        ORDER BY MacID DESC

        UPDATE #ToolSummary
        SET #ToolSummary.TechRequired=ISNULL(#DT.TechRequired,0)
        FROM #ToolSummary
        LEFT OUTER JOIN #DT ON #DT.MacID=#ToolSummary.MachineID


        -- ================================ MATERIAL CODE ========================
        --SELECT MachineID,MaterialCode INTO #Session
        --FROM [SPLOEE].[dbo].[Session] Session
        --WHERE MachineID IN (SELECT MachineID FROM #ToolSummary)
        --AND SessionStatus='RUNNING'

        --UPDATE #ToolSummary SET
        --	#ToolSummary.MaterialCode=#Session.MaterialCode,
        --	#ToolSummary.MaterialDesc=#Session.MaterialDescription
        --FROM #ToolSummary
        --LEFT OUTER JOIN #Session ON #Session.MachineID=#ToolSummary.MachineID

        ------------------------------------------- Machine Status (LED + Status) ------------------------------------
        ;WITH CTE1 AS (
        SELECT DISTINCT MacInfo.InMacID, MAX(MacInfo.ID) AS MaxID
        FROM [KEPDATALOGGER].[dbo].[LogGetMatInfo] MacInfo
        WHERE MacInfo.InMacID IN (SELECT MachineID FROM #ToolSummary)
        -- WHERE MacInfo.InMacID IN ('MSNLTH09-29','MSNLTH13-11')
        GROUP BY MacInfo.InMacID)
        SELECT CTE1.*,MacLEDGreen,MacLEDYellow,MacLEDRed,MacStatus INTO #MacInfo FROM CTE1
        LEFT JOIN (SELECT ID, InMacID,MacLEDGreen,MacLEDYellow,MacLEDRed,MacStatus FROM [KEPDATALOGGER].[dbo].[LogGetMatInfo]) AS R1
        ON R1.InMacID = CTE1.InMacID and R1.ID = CTE1.MaxID;

        UPDATE #ToolSummary SET
        #ToolSummary.MacLEDGreen=ISNULL(#MacInfo.MacLEDGreen,0),
        #ToolSummary.MacLEDYellow=ISNULL(#MacInfo.MacLEDYellow,0),
        #ToolSummary.MacLEDRed=ISNULL(#MacInfo.MacLEDRed,0),
        #ToolSummary.MacStatus=ISNULL(#MacInfo.MacStatus,0)
        FROM #ToolSummary
        LEFT OUTER JOIN #MacInfo ON #MacInfo.InMacID=#ToolSummary.MachineID

        SELECT * FROM #ToolSummary ORDER BY DurationMins

        DROP TABLE #TL,#ToolLife,#Session,#WCMachineID,#ToolInfo,#ToolSummary,#DT,#MacInfo
        '''
        df = pd.read_sql(query, conn)
        conn.close()

    else:
        data_demo = {'MachineID': ['MSNLTH09-29','MSNLTH13-11'],
                    'Location': ['FMC9','FMC4'],
                    'MaterialCode': ['40039550','40061967'],
                    'MaterialDesc': ['MATERIAL A','MATERIAL B'],
                    'ToolingStation': [202,101],
                    'TotalCounter': [164,75],
                    'PresetCounter': [300,200],
                    'BalanceCounter': [136,125],
                    'DurationMins': [10,135],
                    'TechRequired': [False,False],
                    'MacLEDGreen': [False,False],
                    'MacLEDYellow': [False,False],
                    'MacLEDRed': [False,True],
                    'MacStatus': [0,0]}
        df = pd.DataFrame(data_demo)

    return df

# get tool data (all)
def load_data_all():
    if not DEMO_MODE:
        conn = get_db_connection()
        query = f'''
        SET NOCOUNT ON
        SET ANSI_WARNINGS OFF
        ;

        DECLARE @Plant INT=2100
        ------------------------------------------- ToolCounter ------------------------------------
        SELECT TL.ToolNoId,mmTool.ToolID mmToolID,mmTool.ToolingMaker,TN.MachineId,TN.IdentifyNo,TL.StartCounter,TL.CurrentCounter,TL.TotalCounter, TL.IsActiveTool,
        TL.StartDate, GetDate() CompletedDate,TN.ToolPieces,
        mmTool.ToolingStation,mmTool.ProductGroup,mmTool.ToolingClass,mmTool.ToolingMainCategory, mmTool.ToolingSubCategory, mmTool.SAPCode,
        ISNULL(mmTool.PresetCounter,0)PresetCounter
        INTO #ToolLife FROM ToolLife TL
        INNER JOIN (ToolNo TN INNER JOIN mmTool mmTool ON TN.mmToolID=mmTool.ID)
        ON TL.ToolNoId=TN.Id
        WHERE TN.MachineID LIKE 'MS%'
        AND TL.IsActiveTool=1
        ORDER BY MACHINEID,SAPCode DESC

        --SELECT TL.ToolNoId,mmTool.ToolID mmToolID,mmTool.ToolingMaker,TN.MachineId,TN.IdentifyNo,TL.StartCounter,TL.CurrentCounter,TL.TotalCounter, 0 IsActiveTool,
        --TL.StartDate, TL.CompletedDate,TN.ToolPieces,
        --mmTool.ToolingStation,mmTool.ProductGroup,mmTool.ToolingClass,mmTool.ToolingMainCategory, mmTool.ToolingSubCategory, mmTool.SAPCode,
        --ISNULL(mmTool.PresetCounter,0)PresetCounter
        --INTO #ToolLifeHist FROM ToolLifeHistory TL
        --INNER JOIN (ToolNo TN INNER JOIN mmTool mmTool ON TN.mmToolID=mmTool.ID)
        --ON TL.ToolNoId=TN.Id
        --WHERE TL.ToolNoId IN (SELECT ToolNoID FROM #ToolLife)
        --ORDER BY MACHINEID,SAPCode DESC

        --INSERT INTO #ToolLife SELECT * FROM #ToolLifeHist
        -- drop table #ToolLife,#ToolLifeHist

        ------------------------------------------- Material & Machine Information ------------------------------------
        SELECT Plant, MachineID, Dept, MaterialCode, MaterialDescription, MesCT
        INTO #Session  FROM [SPLOEE].[dbo].[Session]
        WHERE MachineID IN (SELECT DISTINCT MachineID FROM #ToolLife)
        AND SessionStatus='RUNNING' AND Plant=@Plant

        SELECT Plant,Dept,MachineID,MachineNo Location
        INTO #WCMachineID FROM [MDM].[dbo].[WorkCenterMachineID]
        WHERE MachineID IN (SELECT DISTINCT MachineID FROM #ToolLife)
        AND DelFlag=0 AND IsActive=1 AND Plant=@Plant

        ------------------------------------------- ToolLifeDetails In Group ------------------------------------
        SELECT MachineID,ToolNoID,ToolingMainCategory,ToolingSubCategory,ToolingStation,SUM(TotalCounter) TotalCounter,PresetCounter
        INTO #TL FROM #ToolLife
        GROUP BY MachineID,ToolNoID,ToolingMainCategory,ToolingSubCategory,ToolingStation,PresetCounter
        ORDER BY MachineID,ToolingMainCategory,ToolingStation

        SELECT #TL.*,(#TL.PresetCounter-#TL.TotalCounter) Balance, 
        #Session.MesCT,#Session.MaterialCode,#Session.MaterialDescription,
        #WCMachineID.Location,0 DurationMins
        INTO #ToolInfo FROM #TL
        LEFT OUTER JOIN #Session ON #TL.MachineID=#Session.MachineID
        LEFT OUTER JOIN #WCMachineID ON #TL.MachineID=#WCMachineID.MachineID

        ------------------------------------------- Revise ToolCounter (Muratec Data) 27/06/25 ------------------------------------
        UPDATE TI 
        SET 
            TI.PresetCounter = TC.ToolSetPoint,
            TI.Balance = TC.ToolBalance,
            TI.TotalCounter = TC.ToolQty
        FROM 
            #ToolInfo TI 
        INNER JOIN ToolCount TC ON 
            TI.MachineID = TC.MacID
            AND TI.ToolingMainCategory = TC.MainCategory
            AND TI.ToolingStation = TC.ToolStation

        UPDATE #ToolInfo SET Balance=0 WHERE Balance<0
        UPDATE #ToolInfo SET DurationMins=(Balance*MesCT)/60
        ------------------------------------------- ToolLife Summary ------------------------------------
        DECLARE @RowNum INT=1
        DECLARE @TotalRow INT
        SET @TotalRow = (SELECT COUNT(DISTINCT MachineID) from #ToolInfo)

        CREATE TABLE #ToolSummary (
        MachineID NVARCHAR(18),
        Location NVARCHAR(10),
        MaterialCode NVARCHAR(40),
        MaterialDesc NVARCHAR(40),
        ToolingStation INT,
        TotalCounter INT,
        PresetCounter INT,
        BalanceCounter INT,
        DurationMins INT,
        TechRequired BIT,
        MacLEDGreen BIT,
        MacLEDYellow BIT,
        MacLEDRed BIT,
        MacStatus INT
        )

        WHILE @RowNum <= @TotalRow
        BEGIN
            INSERT INTO #ToolSummary SELECT TOP 1 MachineID,Location,MaterialCode,MaterialDescription,
                ToolingStation,TotalCounter,PresetCounter,Balance,DurationMins,0,0,0,0,0 
            FROM #ToolInfo
            WHERE MachineID NOT IN (SELECT MachineID FROM #ToolSummary)
            ORDER BY DurationMins
            SET @RowNum= @RowNum+1
        END

        ------------------------------------------- Technical Request Information ------------------------------------
        DECLARE @ProdnShift INT
        DECLARE @PrevDay INT
        DECLARE @ProdnDate AS DATE

        SELECT TOP 1 @ProdnShift=Shift,@PrevDay=CAST(PreviousDay AS INT) FROM mdm.dbo.TSHIFT
        WHERE Plant=@Plant AND ISNULL(DelFlag,0)=0 AND CAST(getdate() AS TIME)
        BETWEEN StartTime AND EndTime
        SET @ProdnDate = DATEADD(d,-@PrevDay,CAST(getdate() AS DATE))

        SELECT DT.ID,Kep.MacID,DT.TechRequired
        INTO #DT FROM [SPLOEE].[dbo].[OEEDownTime] DT
        LEFT OUTER JOIN [SPLOEE].[dbo].[OEEOUTPUTKEP] Kep ON DT.ID=Kep.ID
        WHERE Kep.ProdnDate=@ProdnDate AND Kep.ProdnShift=@ProdnShift
        AND DT.TechRequired=1
        AND Kep.MacID IN (SELECT MachineID FROM #ToolSummary)
        ORDER BY MacID DESC

        UPDATE #ToolSummary
        SET #ToolSummary.TechRequired=ISNULL(#DT.TechRequired,0)
        FROM #ToolSummary
        LEFT OUTER JOIN #DT ON #DT.MacID=#ToolSummary.MachineID


        -- ================================ MATERIAL CODE ========================
        --SELECT MachineID,MaterialCode INTO #Session
        --FROM [SPLOEE].[dbo].[Session] Session
        --WHERE MachineID IN (SELECT MachineID FROM #ToolSummary)
        --AND SessionStatus='RUNNING'

        --UPDATE #ToolSummary SET
        --	#ToolSummary.MaterialCode=#Session.MaterialCode,
        --	#ToolSummary.MaterialDesc=#Session.MaterialDescription
        --FROM #ToolSummary
        --LEFT OUTER JOIN #Session ON #Session.MachineID=#ToolSummary.MachineID

        ------------------------------------------- Machine Status (LED + Status) ------------------------------------
        ;WITH CTE1 AS (
        SELECT DISTINCT MacInfo.InMacID, MAX(MacInfo.ID) AS MaxID
        FROM [KEPDATALOGGER].[dbo].[LogGetMatInfo] MacInfo
        WHERE MacInfo.InMacID IN (SELECT MachineID FROM #ToolSummary)
        -- WHERE MacInfo.InMacID IN ('MSNLTH09-29','MSNLTH13-11')
        GROUP BY MacInfo.InMacID)
        SELECT CTE1.*,MacLEDGreen,MacLEDYellow,MacLEDRed,MacStatus INTO #MacInfo FROM CTE1
        LEFT JOIN (SELECT ID, InMacID,MacLEDGreen,MacLEDYellow,MacLEDRed,MacStatus FROM [KEPDATALOGGER].[dbo].[LogGetMatInfo]) AS R1
        ON R1.InMacID = CTE1.InMacID and R1.ID = CTE1.MaxID;

        UPDATE #ToolSummary SET
        #ToolSummary.MacLEDGreen=ISNULL(#MacInfo.MacLEDGreen,0),
        #ToolSummary.MacLEDYellow=ISNULL(#MacInfo.MacLEDYellow,0),
        #ToolSummary.MacLEDRed=ISNULL(#MacInfo.MacLEDRed,0),
        #ToolSummary.MacStatus=ISNULL(#MacInfo.MacStatus,0)
        FROM #ToolSummary
        LEFT OUTER JOIN #MacInfo ON #MacInfo.InMacID=#ToolSummary.MachineID


        SELECT
        Location, ToolingMainCategory AS [Turret], ToolingStation AS [Tool], ToolingSubCategory AS [Process], DurationMins AS [Balance (mins)], Balance AS [Balance (pcs)]
        FROM #ToolInfo
        ORDER BY Location, DurationMins

        DROP TABLE #TL,#ToolLife,#Session,#WCMachineID,#ToolInfo,#ToolSummary,#DT,#MacInfo
        --DROP TABLE #DT,#MacInfo
        '''
        df = pd.read_sql(query, conn)
        conn.close()

    else:
        data_demo = {'Location': ['FMC9','FMC9','FMC9'],
                    'Turret': ['RIGHT','RIGHT','RIGHT'],
                    'Tool': ['202','101','505'],
                    'Process': ['OP10 OD FINISH','OP10 OD ROUGH','OP10 ID FINISH'],
                    'Balance (mins)': ['12','12','13'],
                    'Balance (pcs)': ['15','15','17']}
        df = pd.DataFrame(data_demo)

    return df

# get CTQ SpecNo
def get_CTQ_SpecNo(sapcode):
    conn = get_db_connection()
    query = f'''
    SET NOCOUNT ON
    SET ANSI_WARNINGS OFF
    ;

    DECLARE @SAPCODE AS NVARCHAR(100) = '{sapcode}'
    
    SELECT
    BalloonNo
    FROM [QMM].[dbo].[SPCcontrolPlan]
    WHERE 1=1
    AND [ControlPlanId] IN (SELECT [ControlPlanId] FROM [QMM].[dbo].[SPCcontrolPlanGenInfo] WHERE SAPCode = @SAPCODE AND IsActive = 1  AND DEPARTMENT != 'VEND') and CAT in (2,3)
    '''
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# get inspection data
def get_inspection_data(sapcode, specno):
    conn = get_db_connection()
    query = f'''
    SET NOCOUNT ON
    SET ANSI_WARNINGS OFF
    ;

    DECLARE @SAPCODE AS NVARCHAR(100) = '{sapcode}'
    DECLARE @SPECNO AS NVARCHAR(100) = '{specno}'

    --DECLARE @SAPCODE AS NVARCHAR(100) = '40039550'
    --DECLARE @SPECNO AS NVARCHAR(100) = '201'

    ;WITH cte_MinMaxofSpec_temp AS (
                SELECT
                a.[charid]
                ,a.[BalloonNo]
                ,a.[Description]
                ,a.[UppTol]
                ,a.[LowTol]
                ,a.TolSymbol
                ,a.SpecType
                ,CASE   WHEN [Spectype] ='4' THEN 'AC'
                        WHEN [Spectype] ='5' AND IsPassFailGDT = 1 THEN 'AC'
                        WHEN [Spectype] ='6' THEN NULL
                        ELSE a.[maxval]
                END AS [USL]
                ,CASE   WHEN [Spectype] ='3' AND a.[maxval] not in ('99999') THEN '-99999' -- LSL change to -99999 instead of 0
                        WHEN [Spectype] ='4' THEN 'NC'
                        WHEN [Spectype] ='5' AND IsPassFailGDT = 1 THEN 'NC'
                        WHEN [Spectype] ='6' THEN NULL
                        ELSE A.[minval]
                END AS [LSL]
                ,a.[CAT]
                ,a.NomVal
                FROM [QMM].[dbo].[SPCControlPlan] AS a
                WHERE 1=1
                AND [ControlPlanId] IN (SELECT [ControlPlanId] FROM [QMM].[dbo].[SPCcontrolPlanGenInfo] WHERE SAPCode = @SAPCODE AND IsActive = 1  AND DEPARTMENT != 'VEND')
                AND [BalloonNo] = @SPECNO
    ),
    
    CTE_BALLOON AS (
            SELECT
            [CharId]
            ,[LSL]
            ,[USL]
            ,[NomVal]
            , [BalloonNo]
            , [CAT]
            , CASE WHEN [TolSymbol] = '1' THEN CONCAT( REPLACE([Description],'*',''),' ',NomVal,' ± ',[UppTol])
                WHEN [TolSymbol] = '2' THEN CONCAT( REPLACE([Description],'*',''),' ',NomVal,' +',[UppTol], ' / +',[LowTol])
                WHEN [TolSymbol] = '3' THEN CONCAT( REPLACE([Description],'*',''),' ',NomVal,' +',[UppTol], ' / ',[LowTol])
                WHEN [TolSymbol] = '4' THEN CONCAT( REPLACE([Description],'*',''),' ',NomVal,' ',[UppTol], ' / ',[LowTol])
                WHEN [TolSymbol] = '5' THEN CONCAT( REPLACE([Description],'*',''),N' ≥ ',[LowTol])
                WHEN [TolSymbol] = '7' THEN CONCAT( REPLACE([Description],'*',''),' > ',[LowTol])
                WHEN [TolSymbol] = '6' THEN CONCAT( REPLACE([Description],'*',''),N' ≤ ',[UppTol])
                WHEN [TolSymbol] = '8' THEN CONCAT( REPLACE([Description],'*',''),' < ',[UppTol])
                WHEN SpecType = '4' THEN REPLACE([Description],'*','') --PASS FAIL
                WHEN SpecType = '5' THEN CONCAT( REPLACE([Description],'*',''),' < ',[UppTol]) --GDT
                WHEN SpecType = '6' THEN REPLACE([Description],'*','') --REMARK SPEC
                ELSE CONCAT( REPLACE([Description],'*',''),' ',LSL,'~',USL) END AS [Description]
        FROM cte_MinMaxofSpec_temp
    )

    SELECT TOP(30) A.[MeasDate], TRY_CAST(A.[MeasVal] AS NUMERIC(26,4)) AS MeasVal, C.LSL, C.USL,c.[Description],c.CharId, c.BalloonNo, c.CAT
    FROM [QMM].[dbo].[InspResult] AS A

	INNER JOIN [QMM].[dbo].[InspMainInfo] AS B
	ON A.InspId = B.[InspId]
    join CTE_BALLOON C on C.CharId = A.CharId

    WHERE 1=1
	AND B.FormType = 'PROD'
    ORDER BY A.[CharId],A.[MeasDate] DESC --get latest 30 inspection data
    
	OPTION(RECOMPILE);
    '''
    df = pd.read_sql(query, conn)
    conn.close()
    return df