import pyodbc
from dotenv import load_dotenv
import os

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

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

def get_OT_DataLake_db_connection():
    server = os.getenv("OT_Datalake_SQL_SERVER")
    database = os.getenv("OT_Datalake_SQL_DATABASE")
    username = os.getenv("OT_Datalake_SQL_USERNAME")
    password = os.getenv("OT_Datalake_SQL_PASSWORD")

    conn = pyodbc.connect(
        f'DRIVER=ODBC Driver 17 for SQL Server;'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'UID={username};'
        f'PWD={password};'
        # 'Encrypt=yes;'
    )
    return conn

def get_DataMart_db_connection():
    server = os.getenv("Datamart_SQL_SERVER")
    database = os.getenv("Datamart_SQL_DATABASE")
    username = os.getenv("Datamart_SQL_USERNAME")
    password = os.getenv("Datamart_SQL_PASSWORD")

    conn = pyodbc.connect(
        f'DRIVER=ODBC Driver 17 for SQL Server;'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'UID={username};'
        f'PWD={password};'
        # 'Encrypt=yes;'
    )
    return conn

def get_Questdb_connection():
    Qusername = os.getenv("QuestDB_Username")
    Qpassword = os.getenv("QuestDB_Password")
    Qhost = os.getenv("QuestDB_Host")
    Qport =os.getenv("QuestDB_Port")
    Qdatabase = os.getenv("QuestDB_Database")


    # Create SQLAlchemy engine
    engine = create_engine(f'postgresql+psycopg2://{Qusername}:{Qpassword}@{Qhost}:{Qport}/{Qdatabase}')
    return engine

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
        DATEADD(HOUR, 8, TL.StartDate) AS StartDate, GetDate() CompletedDate,TN.ToolPieces,
        mmTool.ToolingStation,mmTool.ProductGroup,mmTool.ToolingClass,mmTool.ToolingMainCategory, mmTool.ToolingSubCategory, mmTool.SAPCode,
        ISNULL(mmTool.PresetCounter,0)PresetCounter,
        mmTool.LoadX_Alm,mmTool.LoadZ_Alm
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
        SELECT MachineID,ToolNoID,ToolingMainCategory,ToolingSubCategory,ToolingStation,SUM(TotalCounter) TotalCounter,PresetCounter,LoadX_Alm,LoadZ_Alm
        INTO #TL FROM #ToolLife
        GROUP BY MachineID,ToolNoID,ToolingMainCategory,ToolingSubCategory,ToolingStation,PresetCounter,LoadX_Alm,LoadZ_Alm
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
        TechRequestMin INT,
        MacLEDGreen BIT,
        MacLEDYellow BIT,
        MacLEDRed BIT,
        MacStatus INT,
        MacStopMins INT,
        LoadPeak_Alm_L BIT,
        LoadPeak_Warn_L BIT,
        LoadPeak_Alm_R BIT,
        LoadPeak_Warn_R BIT,
        )

        WHILE @RowNum <= @TotalRow
        BEGIN
            INSERT INTO #ToolSummary SELECT TOP 1 MachineID,Location,MaterialCode,MaterialDescription,
                ToolingStation,TotalCounter,PresetCounter,Balance,DurationMins,0,0,0,0,0,0,0,0,0,0,0 
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
        SET @ProdnDate = DATEADD(d,-@PrevDay,CAST(getdate() AS DATE))

        SELECT DT.ID,Kep.MacID,DT.TechRequired,
        DATEDIFF(MINUTE, (CASE WHEN UpdateDate IS NULL THEN CreatedDate ELSE UpdateDate END), GetDate()) AS TechRequestMin
        INTO #DT FROM [SPLOEE].[dbo].[OEEDownTime] DT
        LEFT OUTER JOIN [SPLOEE].[dbo].[OEEOUTPUTKEP] Kep ON DT.ID=Kep.ID
        WHERE Kep.ProdnDate=@ProdnDate AND Kep.ProdnShift=@ProdnShift
        AND DT.TechRequired=1
        AND Kep.MacID IN (SELECT MachineID FROM #ToolSummary)
        ORDER BY MacID DESC

        UPDATE #ToolSummary
        SET #ToolSummary.TechRequired=ISNULL(#DT.TechRequired,0),
            #ToolSummary.TechRequestMin=ISNULL(#DT.TechRequestMin,0)
        FROM #ToolSummary
        LEFT OUTER JOIN #DT ON #DT.MacID=#ToolSummary.MachineID

        -- ================================ MATERIAL CODE ========================
        --SELECT MachineID,MaterialCode INTO #Session
        --FROM [SPLOEE].[dbo].[Session] Session
        --WHERE MachineID IN (SELECT MachineID FROM #ToolSummary)
        --AND SessionStatus='RUNNING'

        --UPDATE #ToolSummary SET
        -- #ToolSummary.MaterialCode=#Session.MaterialCode,
        -- #ToolSummary.MaterialDesc=#Session.MaterialDescription
        --FROM #ToolSummary
        --LEFT OUTER JOIN #Session ON #Session.MachineID=#ToolSummary.MachineID

        ------------------------------------------- Machine Stop Duration ------------------------------------
        SELECT Kep.ID,Kep.ProdnDate,Kep.ProdnShift,Kep.MacID,Kep.RecordType, 
        DATEDIFF(MINUTE, (CASE WHEN Kep.RecordType='STOP' THEN Kep.StartTime ELSE GetDate() END), GetDate()) AS MacStopMin
        INTO #MacStatus
        FROM [SPLOEE].[dbo].[OEEOUTPUTKEP] Kep
        JOIN (SELECT MAX(ID) ID, Macid FROM [SPLOEE].[dbo].[OEEOUTPUTKEP] Kep2 
                WHERE Kep2.ProdnDate=@ProdnDate AND Kep2.ProdnShift=@ProdnShift
                Group By Macid) AS Kep2 ON (Kep.ID = Kep2.ID)

        ------------------------------------------- Machine Status (LED + Status) ------------------------------------
        ;WITH CTE1 AS (
        SELECT DISTINCT MacInfo.InMacID, MAX(MacInfo.ID) AS MaxID
        FROM [KEPDATALOGGER].[dbo].[LogGetMatInfo] MacInfo
        WHERE MacInfo.InMacID IN (SELECT MachineID FROM #ToolSummary)
        -- WHERE MacInfo.InMacID IN ('MSNLTH09-29','MSNLTH13-11')
        GROUP BY MacInfo.InMacID)
        SELECT CTE1.*,MacLEDGreen,MacLEDYellow,MacLEDRed,MacStatus,
        LoadPeak_Alm_L,LoadPeak_Warn_L,LoadPeak_Alm_R,LoadPeak_Warn_R 
        INTO #MacInfo FROM CTE1
        LEFT JOIN (SELECT ID, InMacID,MacLEDGreen,MacLEDYellow,MacLEDRed,MacStatus,
                            LoadPeak_Alm_L,LoadPeak_Warn_L,LoadPeak_Alm_R,LoadPeak_Warn_R 
                    FROM [KEPDATALOGGER].[dbo].[LogGetMatInfo]) AS R1
        ON R1.InMacID = CTE1.InMacID and R1.ID = CTE1.MaxID;

        UPDATE #ToolSummary SET
        #ToolSummary.MacLEDGreen=ISNULL(#MacInfo.MacLEDGreen,0),
        #ToolSummary.MacLEDYellow=ISNULL(#MacInfo.MacLEDYellow,0),
        #ToolSummary.MacLEDRed=ISNULL(#MacInfo.MacLEDRed,0),
        #ToolSummary.MacStatus=ISNULL(#MacInfo.MacStatus,0),
        #ToolSummary.LoadPeak_Alm_L=ISNULL(#MacInfo.LoadPeak_Alm_L,0),
        #ToolSummary.LoadPeak_Warn_L=ISNULL(#MacInfo.LoadPeak_Warn_L,0),
        #ToolSummary.LoadPeak_Alm_R=ISNULL(#MacInfo.LoadPeak_Alm_R,0),
        #ToolSummary.LoadPeak_Warn_R=ISNULL(#MacInfo.LoadPeak_Warn_R,0),
        #ToolSummary.MacStopMins=ISNULL(#MacStatus.MacStopMin,0)
        FROM #ToolSummary
        LEFT OUTER JOIN #MacInfo ON #MacInfo.InMacID=#ToolSummary.MachineID
        LEFT OUTER JOIN #MacStatus ON #MacStatus.MacID=#ToolSummary.MachineID

        SELECT * FROM #ToolSummary ORDER BY MacLEDRed DESC,MacLEDYellow DESC,TechRequired desc,MacLEDGreen desc,DurationMins

        -- SELECT * FROM #ToolSummary ORDER BY DurationMins
        -- SELECT * FROM #ToolInfo ORDER BY DurationMins

        DROP TABLE #TL,#ToolLife,#Session,#WCMachineID,#ToolInfo,#ToolSummary,#DT,#MacInfo,#MacStatus
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
                    'TechRequestMin':0,
                    'MacLEDGreen': [False,False],
                    'MacLEDYellow': [False,False],
                    'MacLEDRed': [False,True],
                    'MacStatus': [0,0],
                    'LoadPeak_Alm_L':False,
                    'LoadPeak_Warn_L':False,
                    'LoadPeak_Alm_R':False,
                    'LoadPeak_Warn_R':False,
                    'MacStopMins':'0'}
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
        DATEADD(HOUR, 8, TL.StartDate) AS StartDate, GetDate() CompletedDate,TN.ToolPieces,
        mmTool.ToolingStation,mmTool.ProductGroup,mmTool.ToolingClass,mmTool.ToolingMainCategory, mmTool.ToolingSubCategory, mmTool.SAPCode,
        ISNULL(mmTool.PresetCounter,0)PresetCounter,
        mmTool.LoadX_Alm,mmTool.LoadZ_Alm
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
        SELECT MachineID,ToolNoID,ToolingMainCategory,ToolingSubCategory,ToolingStation,SUM(TotalCounter) TotalCounter,PresetCounter,StartDate,LoadX_Alm,LoadZ_Alm,mmToolID
        INTO #TL FROM #ToolLife
        GROUP BY MachineID,ToolNoID,ToolingMainCategory,ToolingSubCategory,ToolingStation,PresetCounter,StartDate,LoadX_Alm,LoadZ_Alm,mmToolID
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
        TechRequestMin INT,
        MacLEDGreen BIT,
        MacLEDYellow BIT,
        MacLEDRed BIT,
        MacStatus INT,
        LoadPeak_Alm_L BIT,
        LoadPeak_Warn_L BIT,
        LoadPeak_Alm_R BIT,
        LoadPeak_Warn_R BIT,
        )

        WHILE @RowNum <= @TotalRow
        BEGIN
            INSERT INTO #ToolSummary SELECT TOP 1 MachineID,Location,MaterialCode,MaterialDescription,
                ToolingStation,TotalCounter,PresetCounter,Balance,DurationMins,0,0,0,0,0,0,0,0,0,0 
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

        SELECT DT.ID,Kep.MacID,DT.TechRequired,
        DATEDIFF(MINUTE, (CASE WHEN UpdateDate IS NULL THEN CreatedDate ELSE UpdateDate END), GetDate()) AS TechRequestMin
        INTO #DT FROM [SPLOEE].[dbo].[OEEDownTime] DT
        LEFT OUTER JOIN [SPLOEE].[dbo].[OEEOUTPUTKEP] Kep ON DT.ID=Kep.ID
        WHERE Kep.ProdnDate=@ProdnDate AND Kep.ProdnShift=@ProdnShift
        AND DT.TechRequired=1
        AND Kep.MacID IN (SELECT MachineID FROM #ToolSummary)
        ORDER BY MacID DESC

        UPDATE #ToolSummary
        SET #ToolSummary.TechRequired=ISNULL(#DT.TechRequired,0),
            #ToolSummary.TechRequestMin=ISNULL(#DT.TechRequestMin,0)
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
        SELECT CTE1.*,MacLEDGreen,MacLEDYellow,MacLEDRed,MacStatus,
        LoadPeak_Alm_L,LoadPeak_Warn_L,LoadPeak_Alm_R,LoadPeak_Warn_R 
        INTO #MacInfo FROM CTE1
        LEFT JOIN (SELECT ID, InMacID,MacLEDGreen,MacLEDYellow,MacLEDRed,MacStatus,
                          LoadPeak_Alm_L,LoadPeak_Warn_L,LoadPeak_Alm_R,LoadPeak_Warn_R 
                   FROM [KEPDATALOGGER].[dbo].[LogGetMatInfo]) AS R1
        ON R1.InMacID = CTE1.InMacID and R1.ID = CTE1.MaxID;

        UPDATE #ToolSummary SET
        #ToolSummary.MacLEDGreen=ISNULL(#MacInfo.MacLEDGreen,0),
        #ToolSummary.MacLEDYellow=ISNULL(#MacInfo.MacLEDYellow,0),
        #ToolSummary.MacLEDRed=ISNULL(#MacInfo.MacLEDRed,0),
        #ToolSummary.MacStatus=ISNULL(#MacInfo.MacStatus,0),
        #ToolSummary.LoadPeak_Alm_L=ISNULL(#MacInfo.LoadPeak_Alm_L,0),
        #ToolSummary.LoadPeak_Warn_L=ISNULL(#MacInfo.LoadPeak_Warn_L,0),
        #ToolSummary.LoadPeak_Alm_R=ISNULL(#MacInfo.LoadPeak_Alm_R,0),
        #ToolSummary.LoadPeak_Warn_R=ISNULL(#MacInfo.LoadPeak_Warn_R,0)
        FROM #ToolSummary
        LEFT OUTER JOIN #MacInfo ON #MacInfo.InMacID=#ToolSummary.MachineID


        SELECT
        Location, ToolingMainCategory AS [Turret], ToolingStation AS [Tool], ToolingSubCategory AS [Process], DurationMins AS [Balance (mins)], Balance AS [Balance (pcs)], MachineID, ToolNoID,StartDate,TotalCounter,PresetCounter,LoadX_Alm,LoadZ_Alm,mmToolID
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
    AND [ControlPlanId] IN (SELECT [ControlPlanId] FROM [QMM].[dbo].[SPCcontrolPlanGenInfo] WHERE SAPCode = @SAPCODE AND IsActive = 1  AND DEPARTMENT != 'VEND') and CAT in (2,3) AND SPECTYPE NOT IN (4, 6) AND (IsPassFailGDT != 1 OR IsPassFailGDT IS NULL)
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

def get_OT_Datalake_data(MachineName, Position, ToolingStation,StartDate):
    conn = get_OT_DataLake_db_connection()
    query = """
            SELECT *
                FROM (
                    SELECT *,? ToolingStation,
                    ROW_NUMBER() OVER (
                    PARTITION BY Value ORDER BY TIMESTAMP DESC
                    ) AS Duplicate
                    FROM [OT_DataLake].[dbo].[OT_MS]
                    WHERE NAME LIKE ?
                    AND NAME LIKE '%_bal%'
                    AND [TIMESTAMP] > ?
            --AND [TIMESTAMP] <=CAST(GETDATE() AS DATE)
            ) D
            WHERE Duplicate = 1
            ORDER BY [TIMESTAMP] DESC
            """


    QueryMachineName = f"%{MachineName}%TOOL_%{'L' if Position.upper() == 'LEFT' else 'R'}_T{str(ToolingStation)}%".replace("-","_")

    StartDate = StartDate.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    params = (ToolingStation,QueryMachineName, StartDate)
    cursor = conn.cursor()
    df = pd.read_sql(query, conn,params=params)
    return df

def get_OT_Datalake_data_history(MachineName, Position, ToolingStation,StartDate,EndDate):
    conn = get_OT_DataLake_db_connection()
    query = """
            SELECT *
                FROM (
                    SELECT *,? ToolingStation,
                    ROW_NUMBER() OVER (
                    PARTITION BY Value ORDER BY TIMESTAMP DESC
                    ) AS Duplicate
                    FROM [OT_DataLake].[dbo].[OT_MS]
                    WHERE NAME LIKE ?
                    AND NAME LIKE '%_bal%'
                    AND [TIMESTAMP] > ?
                    AND [TIMESTAMP] <= ?
            ) D
            WHERE Duplicate = 1
            ORDER BY [TIMESTAMP] DESC
            """


    QueryMachineName = f"%{MachineName}%TOOL_%{'L' if Position.upper() == 'LEFT' else 'R'}_T{str(ToolingStation)}%".replace("-","_")
    StartDate = StartDate.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    EndDate = EndDate.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    params = (ToolingStation,QueryMachineName, StartDate, EndDate)
    cursor = conn.cursor()
    df = pd.read_sql(query, conn,params=params)
    return df


def get_questdb_data(Position,StartDate, ToolingStation, MacID):
    engine = get_Questdb_connection()
    QuestDbQuery="""
        SELECT * 
            FROM MuratecStsLog
            WHERE timestamp > :StartDate 
            and ToolNo = :ToolingStation
            and MacID = :MacID
            and Turret = :Turret
            and Run = 3"""
    StartDate = StartDate.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    params = {"StartDate": StartDate, "ToolingStation": int(str(ToolingStation)[0]), "MacID": MacID, "Turret": Position}
    with engine.connect() as conn:
        df = pd.read_sql(text(QuestDbQuery), conn, params=params)
    return df

def get_questdb_data_history(Position,StartDate,EndDate, ToolingStation, MacID):
    engine = get_Questdb_connection()
    QuestDbQuery="""
        SELECT * 
        FROM MuratecStsLog
        WHERE timestamp > :StartDate 
        and timestamp < :EndDate
        and ToolNo = :ToolingStation
        and MacID = :MacID
        and Turret = :Turret
        and Run = 3"""
    StartDate = StartDate.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    EndDate = EndDate.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    params = {"StartDate": StartDate, "EndDate": EndDate, "ToolingStation": int(str(ToolingStation)[0]), "MacID": MacID, "Turret": Position}
    with engine.connect() as conn:
        df = pd.read_sql(text(QuestDbQuery), conn, params=params)
    return df

def merge_OT_DataLake_Questdb(MachineName, Position, ToolingStation,StartDate, AlarmColumn,AlarmFilter,historyFlag=False,EndDate=None):
    if historyFlag:
        if EndDate is None:
            raise ValueError("EndDate must be provided when historyFlag is True")
        OT_DataLake_df = get_OT_Datalake_data_history(MachineName, Position, ToolingStation,StartDate,EndDate)
    else:
        OT_DataLake_df = get_OT_Datalake_data(MachineName, Position, ToolingStation,StartDate)
    if historyFlag:
        Questdb_df = get_questdb_data_history(Position,StartDate, EndDate,ToolingStation, MachineName)
    else:
        Questdb_df = get_questdb_data(Position,StartDate, ToolingStation, MachineName)
    if OT_DataLake_df.empty and Questdb_df.empty:
        return pd.DataFrame()

    Questdb_df.rename(columns={'ToolNo': 'ToolingStation'}, inplace=True)

    Questdb_df['ToolingStation'] = Questdb_df['ToolingStation'].apply(lambda x: int(f"{x}0{x}"))
    Questdb_df['ToolingStationSeqNum'] = Questdb_df['ToolingStation'].astype(str) +'_'+ Questdb_df['SeqNo'].astype(str)
    
    Questdb_df['Timestamp'] = pd.to_datetime(Questdb_df['Timestamp'])
    OT_DataLake_df['TIMESTAMP'] = pd.to_datetime(OT_DataLake_df['TIMESTAMP'])
    CurrentToolCountNQuestdbdf =pd.merge_asof(Questdb_df.sort_values('Timestamp'), OT_DataLake_df.sort_values('TIMESTAMP'), left_on='Timestamp', right_on='TIMESTAMP', direction='backward')
    CurrentToolCountNQuestdbdf['Timestamp'] = pd.to_datetime(CurrentToolCountNQuestdbdf['Timestamp'], format='%d/%m/%Y %H:%M:%S.%f')

    CurrentToolCountNQuestdbdf = CurrentToolCountNQuestdbdf.dropna(subset=['Duplicate'])

    CurrentToolCountNQuestdbdf['VALUE'] =  CurrentToolCountNQuestdbdf['VALUE'].astype(int)
    
    CurrentToolCountNQuestdbdf = CurrentToolCountNQuestdbdf.sort_values(by='Timestamp').reset_index(drop=True)
    
    CurrentToolCountNQuestdbdf['ToolingStation'] = CurrentToolCountNQuestdbdf['ToolingStation_x']
    CurrentToolCountNQuestdbdf = CurrentToolCountNQuestdbdf.drop(columns=['ToolingStation_x', 'ToolingStation_y'])
    
    #filters
    #filter all data that have time diff of 5s and above with next row
    # Calculate time difference between consecutive rows
    # if ToolingStation == 303:
    #     CurrentToolCountNQuestdbdf=CurrentToolCountNQuestdbdf[CurrentToolCountNQuestdbdf['Load_Z'] <= 70]
    # else:
    #     CurrentToolCountNQuestdbdf['time_diff'] = CurrentToolCountNQuestdbdf['Timestamp'].diff().dt.total_seconds()
    #     # Identify indices where the time difference is greater than 5 seconds
    #     indices_to_remove = CurrentToolCountNQuestdbdf.index[CurrentToolCountNQuestdbdf['time_diff'] > 5].tolist()
        
    #     # Also remove the previous row for each identified index
    #     indices_to_remove += [i - 1 for i in indices_to_remove if i - 1 >= 0]
        
    #     # Drop duplicates and sort the indices
    #     indices_to_remove = sorted(set(indices_to_remove))
        
    #     # Drop the rows from the DataFrame

    #     CurrentToolCountNQuestdbdf = CurrentToolCountNQuestdbdf.drop(index=indices_to_remove).reset_index(drop=True)

    #     # Drop the helper column
    #     CurrentToolCountNQuestdbdf = CurrentToolCountNQuestdbdf.drop(columns='time_diff')
        
    #     CurrentToolCountNQuestdbdf['percent_diff'] = abs(CurrentToolCountNQuestdbdf['SpdlSpd_RPM'] - CurrentToolCountNQuestdbdf['SpdlSpd_RPM_SP']) / CurrentToolCountNQuestdbdf['SpdlSpd_RPM_SP'] * 100
    #     CurrentToolCountNQuestdbdf=CurrentToolCountNQuestdbdf[CurrentToolCountNQuestdbdf['percent_diff'] <= 2]
    AlarmFilter = AlarmFilter*1.1 # add 10% buffer to alarm filter
    CurrentToolCountNQuestdbdf=CurrentToolCountNQuestdbdf[CurrentToolCountNQuestdbdf[AlarmColumn] <= AlarmFilter]


    #CurrentToolCountNQuestdbdf = CurrentToolCountNQuestdbdf[CurrentToolCountNQuestdbdf[selectedColumn]<=CutOffValue]

    return CurrentToolCountNQuestdbdf

def get_historical_data(MachineName, Position, ToolingStation, StartDate, EndDate):
    if not DEMO_MODE:
        conn = get_db_connection()
        query = f'''
        SET NOCOUNT ON
        SET ANSI_WARNINGS OFF
        ;

        DECLARE @Plant INT=2100
        DECLARE @sDate DateTime, @eDate DateTime
        DECLARE @MacID AS NVARCHAR(18)
        DECLARE @MainCategory AS NVARCHAR(10)
        DECLARE @ToolStation AS INT

        SET @sDate='{StartDate}'
        SET @eDate='{EndDate}'

        SET @MacID='{MachineName}'
        SET @MainCategory='{Position}'
        SET @ToolStation={ToolingStation}
        ------------------------------------------- ToolCounter ------------------------------------
        SELECT TL.ToolNoId,mmTool.ToolID mmToolID,mmTool.ToolingMaker,TN.MachineId,TN.IdentifyNo,TL.StartCounter,TL.CurrentCounter,TL.TotalCounter,
        DATEADD(HOUR, 8, TL.StartDate) AS StartDate, DATEADD(HOUR, 8, TL.CompletedDate) AS CompletedDate,TN.ToolPieces,
        mmTool.ToolingStation,mmTool.ProductGroup,mmTool.ToolingClass,mmTool.ToolingMainCategory, mmTool.ToolingSubCategory, mmTool.SAPCode,
        ISNULL(mmTool.PresetCounter,0)PresetCounter,
        mmTool.LoadX_Alm,mmTool.LoadZ_Alm
        INTO #ToolLife FROM ToolLifeHistory TL
        INNER JOIN (ToolNo TN INNER JOIN mmTool mmTool ON TN.mmToolID=mmTool.ID)
        ON TL.ToolNoId=TN.Id
        WHERE TN.MachineID LIKE 'MS%'
        AND TL.ToolNoId NOT IN (SELECT DISTINCT ToolNoID FROM ToolLife)
        AND TN.MachineId=@MacID
        AND mmTool.ToolingMainCategory=@MainCategory
        AND mmTool.ToolingStation=@ToolStation
        AND DATEADD(HOUR, 8, TL.StartDate) BETWEEN @sDate AND @eDate
        AND TL.Delflag = 0
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
        SELECT MachineID,ToolNoID,ToolingMainCategory,ToolingSubCategory,ToolingStation,min(StartDate)StartDate,max(CompletedDate)CompletedDate,
        SUM(TotalCounter) TotalCounter,Max(PresetCounter)PresetCounter,max(LoadX_Alm)LoadX_Alm,max(LoadZ_Alm)LoadZ_Alm,mmToolID
        INTO #TL FROM #ToolLife
        GROUP BY MachineID,ToolNoID,ToolingMainCategory,ToolingSubCategory,ToolingStation,mmToolID
        ORDER BY MachineID,ToolingMainCategory,ToolingStation

        SELECT #TL.*, 
        #Session.MesCT,#Session.MaterialCode,#Session.MaterialDescription,
        #WCMachineID.Location
        INTO #ToolInfo FROM #TL
        LEFT OUTER JOIN #Session ON #TL.MachineID=#Session.MachineID
        LEFT OUTER JOIN #WCMachineID ON #TL.MachineID=#WCMachineID.MachineID

        SELECT
        Location, ToolingMainCategory AS [Turret], ToolingStation AS [Tool], ToolingSubCategory AS [Process], MachineID, ToolNoID,StartDate,TotalCounter,PresetCounter,LoadX_Alm,LoadZ_Alm, CompletedDate ,mmToolID
        FROM #ToolInfo
        Where TotalCounter > 0
        ORDER BY ToolNoID Desc 

        DROP TABLE #TL,#ToolLife,#Session,#WCMachineID,#ToolInfo
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

def get_KPI_Data(MachineName):

    if not DEMO_MODE:
        query = f'''
        SELECT mmTool.ToolID mmToolID,mmTool.ToolingMaker,TN.MachineId,TN.Year,TN.Month,
        SUM(TL.TotalCounter) TotalCounter, SUM(TL.TotalCounter)/COUNT(DISTINCT ToolNoID) AvgCnt,mmTool.PresetCounter,
        mmTool.ToolingStation,mmTool.ProductGroup,mmTool.ToolingClass,mmTool.ToolingMainCategory, mmTool.ToolingSubCategory, mmTool.SAPCode
        FROM ToolLifeHistory TL
        inner JOIN (ToolNo TN inner JOIN mmTool mmTool ON TN.mmToolID=mmTool.ID)
        ON TL.ToolNoId=TN.Id
        LEFT JOIN SPLOEE.DBO.OEEDownTime DT ON TL.OEEOutputKepID = DT.ID
        WHERE TN.MachineId = ? --AND TL.CreatedBy='OPCROUTER'
        AND TL.CreatedDate >= '2025-05-25 00:00:00.000' 
        AND FORMAT(TL.CreatedDate, 'yyyyMM') >= FORMAT(DATEADD(MONTH, -6, GETDATE()), 'yyyyMM')
        -- AND ToolingMainCategory='LEFT' AND ToolingStation=303
        AND TL.CreatedDate NOT BETWEEN '2025/06/01' and '2025/06/02'
        AND TL.ToolNoId NOT IN (SELECT DISTINCT ToolNoID FROM ToolLife)
        AND TL.ToolNoId NOT IN  (5649,5671,5652,5651) -- Testing Data 
        AND TL.TotalCounter > mmTool.PresetCounter * 0.2
        AND TL.Delflag = 0
        GROUP BY mmTool.ToolID,mmTool.ToolingMaker,TN.MachineId,TN.Year,TN.Month,mmTool.PresetCounter,
        mmTool.ToolingStation,mmTool.ProductGroup,mmTool.ToolingClass,mmTool.ToolingMainCategory, mmTool.ToolingSubCategory, mmTool.SAPCode
        ORDER BY mmTool.ToolingMainCategory,mmTool.ToolingStation,TN.Month
        '''
        params = (MachineName)
        conn = get_db_connection()
        df = pd.read_sql(query, conn,params=params)
        conn.close()

        return df
    
def get_History_Inspection_Data(MachineName,StartDate, EndDate):
    query = f'''
    SELECT *
    FROM fact.MES_QMM_InspectionData
    WHERE measdate BETWEEN ? AND DATEADD(DAY, 1, ?)
        AND cat IN ('CTQ', 'CTP')
        AND MachineId = ?
    ORDER BY charid desc
        , MeasDate desc
        , SampleNo
        , SubSampleNo
    '''
    params = (StartDate,EndDate,MachineName)
    conn = get_DataMart_db_connection()
    df = pd.read_sql(query, conn,params=params)
    conn.close()

    return df

def get_questdb_offset_history(MachineName, Position, StartDate, EndDate,ToolNo):
    engine = get_Questdb_connection()
    QuestDbQuery="""
           SELECT * 
            FROM MuratecStsLog
            WHERE timestamp > :StartDate 
            and timestamp < :CompletedDate
            and run  = 3 
            and toolno = :ToolNo
            and Turret = :Turret
            and MacID = :MacID 
            order by timestamp"""
    
    StartDate = StartDate.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    EndDate = EndDate.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    params = {"StartDate": StartDate,"CompletedDate":EndDate,"Turret":Position,"ToolNo":ToolNo, "MacID": MachineName}
    with engine.connect() as conn:
        df = pd.read_sql(text(QuestDbQuery), conn, params=params)
    return df