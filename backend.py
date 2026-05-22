#%%
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
def load_data(limit: int = 1000, plant_code: int = 2100):
    if not DEMO_MODE:
        conn = get_db_connection()
        query = '''
        SET NOCOUNT ON
        SET ANSI_WARNINGS OFF
        ;

        -- 01/01/9999 Add in TechCall with MHA/Mac Error
        -- 01/01/9999 Add in ToolLifePrediction
        -- 06/11/2025 Add in Machine without ToolLife information (Only for Technical Call Function)
        -- 11/11/2025 Add in Material information
        -- 04/05/2026 Revise new MDM
        -- 22/05/2026 PresetCounter sourced from MDM.dbo.tTOOLLIFE

        DECLARE @Plant INT
        SET @Plant = ?

        ------------------------------------------- Step 1: Tool Life Data ------------------------------------
        -- ToolMaterialMachine 的 Unique Key: Plant + ToolNo + Material + MachineID + ToolingStation + Remark1
        -- 必须加上 ToolLife.Material = TMM.Material 才能 1:1 对应，避免数据乘数膨胀

        SELECT
            TL.Id                                           AS ToolLifeId,
            TL.ToolNoID,
            TN.MachineId,
            TN.ToolCode,
            TN.ToolingStation,
            ISNULL(TMM.Remark1, TN.Remark1)                 AS ToolingMainCategory,
            ISNULL(TMM.Remark2, TN.Remark2)                 AS ToolingSubCategory,
            TL.TotalCounter,
            -- ▼ PresetCounter from MDM.tTOOLLIFE instead of ToolLife
            ISNULL(TLM.ToolLife, 0)                         AS PresetCounter,
            (ISNULL(TLM.ToolLife, 0) - TL.TotalCounter)     AS Balance,
            DATEADD(HOUR, 8, TL.StartDate)                  AS StartDate,
            T.ToolNo                                        AS mmToolID,
            VM.CostPerUOM                                   AS UnitPrice,
            0                                               AS LoadX_Alm,
            0                                               AS LoadZ_Alm
        INTO #ToolLife
        FROM [SPLOEELOT].[dbo].[ToolLife] TL
        INNER JOIN [SPLOEELOT].[dbo].[ToolNo] TN
            ON  TL.ToolNoID = TN.Id
            AND ISNULL(TN.Delflag, 0) = 0
        INNER JOIN [MDM].[dbo].[TTOOL] T
            ON  TN.ToolCode = T.ToolNo
            AND T.Plant     = @Plant
            AND ISNULL(T.DelFlag, 0) = 0
        LEFT JOIN [MDM].[dbo].[tTOOLLIFE] TLM
            ON  TLM.ToolNo  = TN.ToolCode
            AND TLM.Plant   = @Plant
            AND ISNULL(TLM.DelFlag, 0) = 0
        LEFT JOIN [MDM].[dbo].[ToolMaterialMachine] TMM
            ON  TMM.ToolNo         = TN.ToolCode
            AND TMM.MachineID      = TN.MachineId
            AND TMM.Material       = TL.Material
            AND TMM.ToolingStation = TN.ToolingStation
            AND TMM.Remark1        = TN.Remark1
            AND TMM.Remark2        = TN.Remark2
            AND TMM.Plant          = @Plant
            AND TMM.IsDeleted      = 0
        LEFT JOIN (
            SELECT Plant, ToolNo, CostPerUOM,
                ROW_NUMBER() OVER (PARTITION BY Plant, ToolNo ORDER BY ValidFrom DESC) AS rn
            FROM [MDM].[dbo].[TOOLVSMAKER]
            WHERE IsDeleted = 0
        ) VM
            ON  VM.ToolNo = TN.ToolCode
            AND VM.Plant  = @Plant
            AND VM.rn     = 1
        WHERE TN.MachineId LIKE 'MS%'
        AND TL.IsActiveTool = 1
        AND ISNULL(TL.Delflag, 0) = 0

        ------------------------------------------- Step 2: Session (MesCT, Material) ------------------------------------
        SELECT MachineID, MesCT, MaterialCode, MaterialDescription
        INTO #Session
        FROM [SPLOEE].[dbo].[Session]
        WHERE MachineID IN (SELECT DISTINCT MachineId FROM #ToolLife)
        AND SessionStatus = 'RUNNING'
        AND Plant = CAST(@Plant AS NVARCHAR)

        ------------------------------------------- Step 3: Machine Location ------------------------------------
        SELECT MachineID, MachineNo AS Location
        INTO #WCMachineID
        FROM [MDM].[dbo].[WorkCenterMachineID]
        WHERE MachineID IN (SELECT DISTINCT MachineId FROM #ToolLife)
        AND DelFlag  = 0
        AND isActive = 1
        AND Plant    = @Plant

        ------------------------------------------- Step 4: Combine into ToolInfo ------------------------------------
        SELECT
            TL.ToolNoID,
            TL.MachineId,
            TL.ToolingStation,
            TL.ToolingMainCategory,
            TL.ToolingSubCategory,
            TL.TotalCounter,
            TL.PresetCounter,
            CASE WHEN TL.Balance < 0 THEN 0 ELSE TL.Balance END AS Balance,
            TL.StartDate,
            TL.mmToolID,
            TL.LoadX_Alm,
            TL.LoadZ_Alm,
            TL.UnitPrice,
            S.MesCT,
            S.MaterialCode,
            S.MaterialDescription,
            W.Location,
            CASE
                WHEN TL.Balance <= 0 THEN 0
                ELSE CONVERT(INT, (TL.Balance * ISNULL(S.MesCT, 0)) / 60) 
            END AS DurationMins
        INTO #ToolInfo
        FROM #ToolLife TL
        LEFT JOIN #Session     S ON S.MachineID = TL.MachineId
        LEFT JOIN #WCMachineID W ON W.MachineID = TL.MachineId

        ------------------------------------------- Step 5: Muratec ToolCount Override ------------------------------------
        --UPDATE TI
        --SET
        --    TI.PresetCounter = TC.ToolSetPoint,
        --    TI.Balance       = TC.ToolBalance,
        --    TI.TotalCounter  = TC.ToolQty,
        --    TI.DurationMins  = CASE
        --                           WHEN TC.ToolBalance <= 0 THEN 0
        --                           ELSE (TC.ToolBalance * ISNULL(TI.MesCT, 0)) / 60
        --                       END
        --FROM #ToolInfo TI
        --INNER JOIN ToolCount TC
        --    ON  TC.MacID        = TI.MachineId
        --    AND TC.MainCategory = TI.ToolingMainCategory
        --    AND TC.ToolStation  = TI.ToolingStation

        UPDATE #ToolInfo SET Balance = 0 WHERE Balance < 0

        ------------------------------------------- Step 6: Tool Summary (Add each Mac Top1 into Summary Table) ------------------------------------
        DECLARE @RowNum   INT = 1
        DECLARE @TotalRow INT  = (SELECT COUNT(DISTINCT MachineId) FROM #ToolInfo)

        CREATE TABLE #ToolSummary (
            MachineID       NVARCHAR(18),
            Location        NVARCHAR(10),
            MaterialCode    NVARCHAR(40),
            MaterialDesc    NVARCHAR(40),
            ToolingStation  INT,
            TotalCounter    INT,
            PresetCounter   INT,
            BalanceCounter  INT,
            DurationMins    INT,
            TechRequired    BIT,
            TechRequestMin  INT,
            MacErrorType    INT,
            MacLEDGreen     BIT,
            MacLEDYellow    BIT,
            MacLEDRed       BIT,
            MacStatus       INT,
            MacStopMins     INT,
            LoadPeak_Alm_L  BIT,
            LoadPeak_Warn_L BIT,
            LoadPeak_Alm_R  BIT,
            LoadPeak_Warn_R BIT,
            MacWithLED      BIT
        )

        WHILE @RowNum <= @TotalRow
        BEGIN
            INSERT INTO #ToolSummary
            SELECT TOP 1
                MachineId, Location, MaterialCode, MaterialDescription,
                ToolingStation, TotalCounter, PresetCounter, Balance, DurationMins,
                0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
            FROM #ToolInfo
            WHERE MachineId NOT IN (SELECT MachineID FROM #ToolSummary)
            ORDER BY DurationMins
            SET @RowNum = @RowNum + 1
        END

        ------------------------------------------- Special handle: Machine without ToolLife (Tech Call only) - Start ------------------------------------
        -- 06/11/2025 Add in Machine without ToolLife information (Only for Technical Call Function)
        -- 11/11/2025 Add in Material information
        INSERT INTO #ToolSummary
        SELECT
            MacInfo.InMacID,
            WC.MachineNo        AS Location,
            MacInfo.pMatCode,
            MacInfo.pMatDesc,
            9999, 9999, 9999, 9999, 9999,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            MacInfo.MacWithLED
        FROM [KEPDATALOGGER].[dbo].[LogGetMatInfo] MacInfo
        JOIN [MDM].[dbo].[WorkCenterMachineID] WC
            ON  MacInfo.InMacID = WC.MachineID
            AND WC.Plant        = @Plant
            AND WC.Dept         = 'MS'
            AND WC.isActive     = 1
            AND WC.DelFlag      = 0
        WHERE MacInfo.ID IN (
            SELECT MAX(ID)
            FROM [KEPDATALOGGER].[dbo].[LogGetMatInfo]
            WHERE InMacID NOT IN (SELECT MachineID FROM #ToolSummary)
            GROUP BY InMacID
        )
        ------------------------------------------- Special handle: Machine without ToolLife - End ------------------------------------

        ------------------------------------------- Step 7: Tech Request ------------------------------------
        DECLARE @ProdnShift INT
        DECLARE @PrevDay    INT
        DECLARE @ProdnDate  DATE

        SELECT TOP 1
            @ProdnShift = Shift,
            @PrevDay    = CAST(PreviousDay AS INT)
        FROM [MDM].[dbo].[TSHIFT]
        WHERE Plant = @Plant
        AND ISNULL(DelFlag, 0) = 0
        AND CAST(GETDATE() AS TIME) BETWEEN StartTime AND EndTime

        SET @ProdnDate = DATEADD(d, -@PrevDay, CAST(GETDATE() AS DATE))

        SELECT
            Kep.MacID,
            DT.TechRequired,
            DATEDIFF(MINUTE,
                CASE WHEN DT.UpdateDate IS NULL THEN DT.CreatedDate ELSE DT.UpdateDate END,
                GETDATE()
            ) AS TechRequestMin,
            CASE WHEN DT.DTReason LIKE '%MHA%' THEN 2 ELSE 1 END AS MacErrorType
        INTO #DT
        FROM [SPLOEE].[dbo].[OEEDownTime] DT
        LEFT JOIN [SPLOEE].[dbo].[OEEOutputKEP] Kep ON DT.ID = Kep.ID
        WHERE Kep.ProdnDate = @ProdnDate
        AND Kep.ProdnShift  = @ProdnShift
        AND DT.TechRequired = 1
        AND DT.Status       = 'OPEN'
        AND Kep.MacID IN (SELECT MachineID FROM #ToolSummary)

        UPDATE #ToolSummary
        SET TechRequired   = ISNULL(D.TechRequired, 0),
            TechRequestMin = ISNULL(D.TechRequestMin, 0),
            MacErrorType   = ISNULL(D.MacErrorType, 0)
        FROM #ToolSummary
        LEFT JOIN #DT D ON D.MacID = #ToolSummary.MachineID

        ------------------------------------------- Step 8: Machine LED & Status ------------------------------------
        ;WITH CTE_Mac AS (
            SELECT InMacID, MAX(ID) AS MaxID
            FROM [KEPDATALOGGER].[dbo].[LogGetMatInfo]
            WHERE InMacID IN (SELECT MachineID FROM #ToolSummary)
            GROUP BY InMacID
        )
        SELECT
            C.InMacID,
            L.MacLEDGreen, L.MacLEDYellow, L.MacLEDRed, L.MacStatus,
            L.LoadPeak_Alm_L, L.LoadPeak_Warn_L, L.LoadPeak_Alm_R, L.LoadPeak_Warn_R,
            L.MacWithLED
        INTO #MacInfo
        FROM CTE_Mac C
        LEFT JOIN [KEPDATALOGGER].[dbo].[LogGetMatInfo] L
            ON L.InMacID = C.InMacID AND L.ID = C.MaxID

        UPDATE #ToolSummary
        SET MacWithLED      = ISNULL(M.MacWithLED, 0),
            MacLEDGreen     = ISNULL(M.MacLEDGreen, 0),
            MacLEDYellow    = ISNULL(M.MacLEDYellow, 0),
            MacLEDRed       = ISNULL(M.MacLEDRed, 0),
            MacStatus       = ISNULL(M.MacStatus, 0),
            LoadPeak_Alm_L  = ISNULL(M.LoadPeak_Alm_L, 0),
            LoadPeak_Warn_L = ISNULL(M.LoadPeak_Warn_L, 0),
            LoadPeak_Alm_R  = ISNULL(M.LoadPeak_Alm_R, 0),
            LoadPeak_Warn_R = ISNULL(M.LoadPeak_Warn_R, 0)
        FROM #ToolSummary
        LEFT JOIN #MacInfo M ON M.InMacID = #ToolSummary.MachineID

        ------------------------------------------- Special handle: No LED machine, MacStatus=3 force Green ------------------------------------
        -- 06/11/2025 Add in Machine without ToolLife information (Only for Technical Call Function)
        UPDATE #ToolSummary
        SET MacLEDGreen  = 1,
            MacLEDRed    = 0,
            MacLEDYellow = 0
        WHERE MacStatus = 3
        AND MacWithLED  = 0

        -- UPDATE #ToolSummary SET MacLEDRed=1,MacLEDGreen=0,MacLEDYellow=0
        -- WHERE MacStatus=0 AND MacWithLED=0

        ------------------------------------------- Final Output ------------------------------------
        SELECT
            TS.*,
            LG.EmpNo,
            LG.EmpName
        FROM #ToolSummary TS
        LEFT JOIN [SPLOEE].[dbo].[LOGIN] LG
            ON  LG.MacID    = TS.MachineID
            AND LG.Status   = 'ONLINE'
            AND LG.Dept     = 'MS'
            AND LG.EmpType  = 'OPERATOR'
        ORDER BY
            MacLEDRed    DESC,
            MacLEDYellow DESC,
            TechRequired DESC,
            MacLEDGreen  DESC,
            DurationMins

        DROP TABLE #ToolLife, #Session, #WCMachineID, #ToolInfo, #ToolSummary, #DT, #MacInfo
        '''
        df = pd.read_sql(query, conn, params=(plant_code,))
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
                    'MacStopMins':'0',
                    'MacErrorType':'1',
                    'EmpNo':'wesd1324',
                    'EmpName':'Abu'}
        df = pd.DataFrame(data_demo)

    return df

# get tool data (all)
def load_data_all(plant_code: int = 2100):
    if not DEMO_MODE:
        conn = get_db_connection()
        query = '''
        SET NOCOUNT ON
        SET ANSI_WARNINGS OFF
        ;

        DECLARE @Plant INT
        SET @Plant = ?

        ------------------------------------------- Step 1: Tool Life Data ------------------------------------
        -- ToolMaterialMachine 的 Unique Key: Plant + ToolNo + Material + MachineID + ToolingStation + Remark1
        -- 必须加上 ToolLife.Material = TMM.Material 才能 1:1 对应，避免数据乘数膨胀

        SELECT
            TL.Id                                       AS ToolLifeId,
            TL.ToolNoID,
            TN.MachineId,
            TN.ToolCode,
            TN.ToolingStation,
            ISNULL(TMM.Remark1, TN.Remark1)             AS ToolingMainCategory,
            ISNULL(TMM.Remark2, TN.Remark2)             AS ToolingSubCategory,
            TL.TotalCounter,
            -- ▼ 改为从 MDM.dbo.tTOOLLIFE 读取 PresetCounter
            ISNULL(TLM.ToolLife, 0)                     AS PresetCounter,
            (ISNULL(TLM.ToolLife, 0) - TL.TotalCounter) AS Balance,
            DATEADD(HOUR, 8, TL.StartDate)              AS StartDate,
            T.ToolNo                                    AS mmToolID,
            VM.CostPerUOM                               AS UnitPrice,
            0                                           AS LoadX_Alm,
            0                                           AS LoadZ_Alm
        INTO #ToolLife
        FROM [SPLOEELOT].[dbo].[ToolLife] TL
        INNER JOIN [SPLOEELOT].[dbo].[ToolNo] TN
            ON TL.ToolNoID = TN.Id
            AND ISNULL(TN.Delflag, 0) = 0
        INNER JOIN [MDM].[dbo].[TTOOL] T
            ON TN.ToolCode = T.ToolNo
            AND T.Plant    = @Plant
            AND ISNULL(T.DelFlag, 0) = 0
        -- ▼ 新增：从 tTOOLLIFE 获取 ToolLife（PresetCounter）
        LEFT JOIN [MDM].[dbo].[tTOOLLIFE] TLM
            ON  TLM.ToolNo  = TN.ToolCode
            AND TLM.Plant   = @Plant
            AND ISNULL(TLM.DelFlag, 0) = 0
        LEFT JOIN [MDM].[dbo].[ToolMaterialMachine] TMM
            ON  TMM.ToolNo         = TN.ToolCode
            AND TMM.MachineID      = TN.MachineId
            AND TMM.Material       = TL.Material
            AND TMM.ToolingStation = TN.ToolingStation
            AND TMM.Remark1        = TN.Remark1
            AND TMM.Remark2        = TN.Remark2
            AND TMM.Plant          = @Plant
            AND TMM.IsDeleted      = 0
        LEFT JOIN (
            SELECT Plant, ToolNo, CostPerUOM,
                ROW_NUMBER() OVER (PARTITION BY Plant, ToolNo ORDER BY ValidFrom DESC) AS rn
            FROM [MDM].[dbo].[TOOLVSMAKER]
            WHERE IsDeleted = 0
        ) VM
            ON  VM.ToolNo = TN.ToolCode
            AND VM.Plant  = @Plant
            AND VM.rn     = 1
        WHERE TN.MachineId LIKE 'MS%'
        AND TL.IsActiveTool = 1
        AND ISNULL(TL.Delflag, 0) = 0
        -- AND TL.PresetCounter = 0  -- 可移除此过滤条件
        ORDER BY TN.MachineId

        -- DROP TABLE #ToolLife
        -- select * from #ToolLife
        ------------------------------------------- Step 2: Session (MesCT, Material) ------------------------------------
        SELECT MachineID, MesCT, MaterialCode, MaterialDescription
        INTO #Session
        FROM [SPLOEE].[dbo].[Session]
        WHERE MachineID IN (SELECT DISTINCT MachineId FROM #ToolLife)
        AND SessionStatus = 'RUNNING'
        AND Plant = CAST(@Plant AS NVARCHAR)

        ------------------------------------------- Step 3: Machine Location ------------------------------------
        SELECT MachineID, MachineNo AS Location
        INTO #WCMachineID
        FROM [MDM].[dbo].[WorkCenterMachineID]
        WHERE MachineID IN (SELECT DISTINCT MachineId FROM #ToolLife)
        AND DelFlag  = 0
        AND isActive = 1
        AND Plant    = @Plant
        
        ------------------------------------------- Step 4: Combine into ToolInfo ------------------------------------
        SELECT
            TL.ToolNoID,
            TL.MachineId,
            TL.ToolingStation,
            TL.ToolingMainCategory,
            TL.ToolingSubCategory,
            TL.TotalCounter,
            TL.PresetCounter,
            CASE WHEN TL.Balance < 0 THEN 0 ELSE TL.Balance END    AS Balance,
            TL.StartDate,
            TL.mmToolID,
            TL.LoadX_Alm,
            TL.LoadZ_Alm,
            TL.UnitPrice,
            S.MesCT,
            S.MaterialCode,
            S.MaterialDescription,
            W.Location,
            CASE
                WHEN TL.Balance <= 0 THEN 0
                ELSE CONVERT(INT, (TL.Balance * ISNULL(S.MesCT, 0)) / 60) 
            END                                                     AS DurationMins
        INTO #ToolInfo
        FROM #ToolLife TL
        LEFT JOIN #Session     S ON S.MachineID = TL.MachineId
        LEFT JOIN #WCMachineID W ON W.MachineID = TL.MachineId

        ------------------------------------------- Step 5: Muratec ToolCount Override ------------------------------------
        --UPDATE TI
        --SET
        --    TI.PresetCounter = TC.ToolSetPoint,
        --    TI.Balance       = TC.ToolBalance,
        --    TI.TotalCounter  = TC.ToolQty,
        --    TI.DurationMins  = CASE
        --                           WHEN TC.ToolBalance <= 0 THEN 0
        --                           ELSE (TC.ToolBalance * ISNULL(TI.MesCT, 0)) / 60
        --                       END
        --FROM #ToolInfo TI
        --INNER JOIN ToolCount TC
        --    ON  TC.MacID        = TI.MachineId
        --    AND TC.MainCategory = TI.ToolingMainCategory
        --    AND TC.ToolStation  = TI.ToolingStation

        UPDATE #ToolInfo SET Balance = 0 WHERE Balance < 0

        ------------------------------------------- Step 6: Tool Summary (for LED/Status) ------------------------------------
        DECLARE @RowNum   INT = 1
        DECLARE @TotalRow INT  = (SELECT COUNT(DISTINCT MachineId) FROM #ToolInfo)

        CREATE TABLE #ToolSummary (
            MachineID       NVARCHAR(18),
            Location        NVARCHAR(10),
            MaterialCode    NVARCHAR(40),
            MaterialDesc    NVARCHAR(40),
            ToolingStation  INT,
            TotalCounter    INT,
            PresetCounter   INT,
            BalanceCounter  INT,
            DurationMins    INT,
            TechRequired    BIT,
            TechRequestMin  INT,
            MacLEDGreen     BIT,
            MacLEDYellow    BIT,
            MacLEDRed       BIT,
            MacStatus       INT,
            LoadPeak_Alm_L  BIT,
            LoadPeak_Warn_L BIT,
            LoadPeak_Alm_R  BIT,
            LoadPeak_Warn_R BIT
        )

        WHILE @RowNum <= @TotalRow
        BEGIN
            INSERT INTO #ToolSummary
            SELECT TOP 1
                MachineId, Location, MaterialCode, MaterialDescription,
                ToolingStation, TotalCounter, PresetCounter, Balance, DurationMins,
                0, 0, 0, 0, 0, 0, 0, 0, 0, 0
            FROM #ToolInfo
            WHERE MachineId NOT IN (SELECT MachineID FROM #ToolSummary)
            ORDER BY DurationMins
            SET @RowNum = @RowNum + 1
        END

        ------------------------------------------- Step 7: Tech Request ------------------------------------
        DECLARE @ProdnShift INT
        DECLARE @PrevDay    INT
        DECLARE @ProdnDate  DATE

        SELECT TOP 1
            @ProdnShift = Shift,
            @PrevDay    = CAST(PreviousDay AS INT)
        FROM [MDM].[dbo].[TSHIFT]
        WHERE Plant = @Plant
        AND ISNULL(DelFlag, 0) = 0
        AND CAST(GETDATE() AS TIME) BETWEEN StartTime AND EndTime

        SET @ProdnDate = DATEADD(d, -@PrevDay, CAST(GETDATE() AS DATE))

        SELECT
            Kep.MacID,
            DT.TechRequired,
            DATEDIFF(MINUTE,
                CASE WHEN DT.UpdateDate IS NULL THEN DT.CreatedDate ELSE DT.UpdateDate END,
                GETDATE()
            ) AS TechRequestMin
        INTO #DT
        FROM [SPLOEE].[dbo].[OEEDownTime] DT
        LEFT JOIN [SPLOEE].[dbo].[OEEOutputKEP] Kep ON DT.ID = Kep.ID
        WHERE Kep.ProdnDate = @ProdnDate
        AND Kep.ProdnShift  = @ProdnShift
        AND DT.TechRequired = 1
        AND Kep.MacID IN (SELECT MachineID FROM #ToolSummary)

        UPDATE #ToolSummary
        SET TechRequired   = ISNULL(D.TechRequired, 0),
            TechRequestMin = ISNULL(D.TechRequestMin, 0)
        FROM #ToolSummary
        LEFT JOIN #DT D ON D.MacID = #ToolSummary.MachineID

        ------------------------------------------- Step 8: Machine LED & Status ------------------------------------
        ;WITH CTE_Mac AS (
            SELECT InMacID, MAX(ID) AS MaxID
            FROM [KEPDATALOGGER].[dbo].[LogGetMatInfo]
            WHERE InMacID IN (SELECT MachineID FROM #ToolSummary)
            GROUP BY InMacID
        )
        SELECT
            C.InMacID,
            L.MacLEDGreen, L.MacLEDYellow, L.MacLEDRed, L.MacStatus,
            L.LoadPeak_Alm_L, L.LoadPeak_Warn_L, L.LoadPeak_Alm_R, L.LoadPeak_Warn_R
        INTO #MacInfo
        FROM CTE_Mac C
        LEFT JOIN [KEPDATALOGGER].[dbo].[LogGetMatInfo] L
            ON L.InMacID = C.InMacID AND L.ID = C.MaxID

        UPDATE #ToolSummary
        SET MacLEDGreen     = ISNULL(M.MacLEDGreen, 0),
            MacLEDYellow    = ISNULL(M.MacLEDYellow, 0),
            MacLEDRed       = ISNULL(M.MacLEDRed, 0),
            MacStatus       = ISNULL(M.MacStatus, 0),
            LoadPeak_Alm_L  = ISNULL(M.LoadPeak_Alm_L, 0),
            LoadPeak_Warn_L = ISNULL(M.LoadPeak_Warn_L, 0),
            LoadPeak_Alm_R  = ISNULL(M.LoadPeak_Alm_R, 0),
            LoadPeak_Warn_R = ISNULL(M.LoadPeak_Warn_R, 0)
        FROM #ToolSummary
        LEFT JOIN #MacInfo M ON M.InMacID = #ToolSummary.MachineID

        ------------------------------------------- Final Output ------------------------------------
        SELECT
            TI.Location,
            TI.ToolingMainCategory              AS [Turret],
            TI.ToolingStation                   AS [Tool],
            TI.ToolingSubCategory               AS [Process],
            TI.DurationMins                     AS [Balance (mins)],
            TI.Balance                          AS [Balance (pcs)],
            TI.MachineId                        AS MachineID,
            TI.ToolNoID,
            TI.StartDate,
            TI.TotalCounter,
            TI.PresetCounter,
            TLP.ToolLife_predicted,
            TLP.Segment_Based_Explanation_md,
            TI.LoadX_Alm,
            TI.LoadZ_Alm,
            TI.mmToolID,
            TI.MesCT,
            TI.UnitPrice
        FROM #ToolInfo TI
        LEFT JOIN [SPLOEELOT].[dbo].[ToolLifePrediction] TLP
            ON  TLP.MachineId          = TI.MachineId
            AND TLP.Turret             = TI.ToolingMainCategory
            AND TLP.ToolingStation     = TI.ToolingStation
            AND TLP.IsLatestPrediction = 1
        ORDER BY TI.Location, TI.DurationMins

        DROP TABLE #ToolLife, #Session, #WCMachineID, #ToolInfo, #ToolSummary, #DT, #MacInfo
        '''
        df = pd.read_sql(query, conn, params=(plant_code,))
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
    print(params)
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
    # else:
    #     OT_DataLake_df = get_OT_Datalake_data(MachineName, Position, ToolingStation,StartDate)
    if historyFlag:
        Questdb_df = get_questdb_data_history(Position,StartDate, EndDate,ToolingStation, MachineName)
    else:
        Questdb_df = get_questdb_data(Position,StartDate, ToolingStation, MachineName)

    if historyFlag:
        
        if Questdb_df.empty:
            return pd.DataFrame()

        if OT_DataLake_df.empty or len(OT_DataLake_df)==0:
            
            Questdb_df.rename(columns={'ToolNo': 'ToolingStation'}, inplace=True)

            Questdb_df['ToolingStation'] = Questdb_df['ToolingStation'].apply(lambda x: int(f"{x}0{x}"))
            Questdb_df['ToolingStationSeqNum'] = Questdb_df['ToolingStation'].astype(str) +'_'+ Questdb_df['SeqNo'].astype(str)
            
            Questdb_df['Timestamp'] = pd.to_datetime(Questdb_df['Timestamp'])
            CurrentToolCountNQuestdbdf = Questdb_df
            CurrentToolCountNQuestdbdf = CurrentToolCountNQuestdbdf.sort_values(by='Timestamp').reset_index(drop=True)
        else:
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
    else:
        if Questdb_df.empty:
            return pd.DataFrame()
        Questdb_df.rename(columns={'ToolNo': 'ToolingStation'}, inplace=True)

        Questdb_df['ToolingStation'] = Questdb_df['ToolingStation'].apply(lambda x: int(f"{x}0{x}"))
        Questdb_df['ToolingStationSeqNum'] = Questdb_df['ToolingStation'].astype(str) +'_'+ Questdb_df['SeqNo'].astype(str)
        
        Questdb_df['Timestamp'] = pd.to_datetime(Questdb_df['Timestamp'])
        CurrentToolCountNQuestdbdf = Questdb_df
        CurrentToolCountNQuestdbdf = CurrentToolCountNQuestdbdf.sort_values(by='Timestamp').reset_index(drop=True)
    
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
    # CurrentToolCountNQuestdbdf=CurrentToolCountNQuestdbdf[CurrentToolCountNQuestdbdf[AlarmColumn] <= AlarmFilter]
    CurrentToolCountNQuestdbdf=CurrentToolCountNQuestdbdf[CurrentToolCountNQuestdbdf[AlarmColumn] >0]


    #CurrentToolCountNQuestdbdf = CurrentToolCountNQuestdbdf[CurrentToolCountNQuestdbdf[selectedColumn]<=CutOffValue]
    print(CurrentToolCountNQuestdbdf)
    return CurrentToolCountNQuestdbdf

def get_historical_data(MachineName, Position, ToolingStation, StartDate, EndDate, plant_code: int = 2100):
    if not DEMO_MODE:
        conn = get_db_connection()
        query = f'''
        SET NOCOUNT ON
        SET ANSI_WARNINGS OFF
        ;

        DECLARE @Plant INT
        SET @Plant = ?
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
        SELECT TL.ToolNoID,mmTool.ToolID mmToolID,mmTool.ToolingMaker,TN.MachineId,TN.IdentifyNo,TL.StartCounter,TL.CurrentCounter,TL.TotalCounter,
        DATEADD(HOUR, 8, TL.StartDate) AS StartDate, DATEADD(HOUR, 8, TL.CompletedDate) AS CompletedDate,TN.ToolPieces,
        mmTool.ToolingStation,mmTool.ProductGroup,mmTool.ToolingClass,mmTool.ToolingMainCategory, mmTool.ToolingSubCategory, mmTool.SAPCode,
        ISNULL(mmTool.PresetCounter,0)PresetCounter,
        mmTool.LoadX_Alm,mmTool.LoadZ_Alm
        INTO #ToolLife FROM ToolLifeHistory TL
        INNER JOIN (ToolNo TN INNER JOIN mmTool mmTool ON TN.mmToolID=mmTool.ID)
        ON TL.ToolNoID=TN.Id
        WHERE TN.MachineID LIKE 'MS%'
        AND TL.ToolNoID NOT IN (SELECT DISTINCT ToolNoID FROM ToolLife)
        AND TN.MachineId=@MacID
        AND mmTool.ToolingMainCategory=@MainCategory
        AND mmTool.ToolingStation=@ToolStation
        AND DATEADD(HOUR, 8, TL.StartDate) BETWEEN @sDate AND @eDate
        AND TL.Delflag = 0
        ORDER BY MACHINEID,SAPCode DESC

        --SELECT TL.ToolNoID,mmTool.ToolID mmToolID,mmTool.ToolingMaker,TN.MachineId,TN.IdentifyNo,TL.StartCounter,TL.CurrentCounter,TL.TotalCounter, 0 IsActiveTool,
        --TL.StartDate, TL.CompletedDate,TN.ToolPieces,
        --mmTool.ToolingStation,mmTool.ProductGroup,mmTool.ToolingClass,mmTool.ToolingMainCategory, mmTool.ToolingSubCategory, mmTool.SAPCode,
        --ISNULL(mmTool.PresetCounter,0)PresetCounter
        --INTO #ToolLifeHist FROM ToolLifeHistory TL
        --INNER JOIN (ToolNo TN INNER JOIN mmTool mmTool ON TN.mmToolID=mmTool.ID)
        --ON TL.ToolNoID=TN.Id
        --WHERE TL.ToolNoID IN (SELECT ToolNoID FROM #ToolLife)
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
        df = pd.read_sql(query, conn, params=(plant_code,))
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

# add all machne flag, add all period flag
def get_KPI_Data(MachineName = None, All_period = False):
    '''
    If MachineName is None, it will return data for all machines.
    If MachineName is provided, it will return data for the specified machine.

    If All_period is True, it will return data for all periods.
    If All_period is False, it will return data for the last 6 months.
    '''

    if not DEMO_MODE:

        machinename = f'''AND TN.MachineId = ?''' if MachineName is not None else ''
        period = f'''AND FORMAT(TL.CreatedDate, 'yyyyMM') >= FORMAT(DATEADD(MONTH, -6, GETDATE()), 'yyyyMM')''' if All_period == False else ''

        query = f'''
        WITH CTE_TL AS (

        SELECT mmTool.ToolID AS mmToolID,mmTool.ToolingMaker,TN.MachineId
        --,TN.Year,TN.Month,
        ,mmTool.PresetCounter,mmTool.ProductGroup,mmTool.SAPCode
        ,mmTool.ToolingMainCategory,mmTool.ToolingStation,mmTool.ToolingClass,mmTool.ToolingSubCategory
        ,ToolNoID,TL.TotalCounter
        ,MAX(TL.CreatedDate) OVER (PARTITION BY ToolNoID) AS [EOLDate]
        FROM ToolLifeHistory TL
        inner JOIN (ToolNo TN inner JOIN mmTool mmTool ON TN.mmToolID=mmTool.ID)
        ON TL.ToolNoID=TN.Id
        LEFT JOIN SPLOEE.DBO.OEEDownTime DT ON TL.OEEOutputKepID = DT.ID

        WHERE 1=1
        {machinename}
        {period}
        AND TL.CreatedDate >= '2025-06-01 00:00:00.000'  --AUTO CHANGE TOOL GO LIVE
        AND TL.CreatedDate NOT BETWEEN '2025/06/01' and '2025/06/02'
        AND TL.ToolNoID NOT IN (SELECT DISTINCT ToolNoID FROM ToolLife)
        AND TL.ToolNoID NOT IN  (5649,5671,5652,5651) -- Testing Data 
        AND TL.TotalCounter > mmTool.PresetCounter * 0.2
        AND TL.ToolNoID NOT IN (SELECT ToolNoID FROM ToolLifeHistory WHERE TotalCounter<0) --DROP DATA DUE TO MACHINE SIDE COUNTER RESET
        AND ISNULL(TL.Delflag,0) = 0

        )

        SELECT 
        mmToolID,ToolingMaker,MachineId
        ,PresetCounter,ProductGroup,SAPCode
        ,ToolingMainCategory,ToolingStation,ToolingClass,ToolingSubCategory

        ,YEAR([EOLDate]) AS Year, MONTH([EOLDate]) AS Month
        ,SUM(TotalCounter) AS TotalCounter, SUM(TotalCounter)/COUNT(DISTINCT ToolNoID) AS AvgCnt
        ,COUNT(DISTINCT ToolNoID) AS NumberofToolReplaced
        FROM CTE_TL

        GROUP BY mmToolID,ToolingMaker,MachineId,YEAR([EOLDate]),MONTH([EOLDate]),PresetCounter,
        ToolingStation,ProductGroup,ToolingClass,ToolingMainCategory,ToolingSubCategory,SAPCode
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
# %%
