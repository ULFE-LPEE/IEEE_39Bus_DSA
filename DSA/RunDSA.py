'''
Author: Matjaz Skrlec
date: 14. 10. 2024
version: 1.0
description: This program is used for creating the DSA learning data
'''

#--------------------------------------------------------------------------------------------------
# imports
import os
import sys
from dotenv import load_dotenv
load_dotenv(override=True)
sys.path.append(os.getenv("PowerfactoryPyFilePath"))
import powerfactory as pf
import DSA.HandleFiles as HandleFiles
import DSA.TSA as TSA
import DSA.SSSA as SSSA
import DSA.FSA as FSA
import DSA.STATIC as STATIC
import parallelisation.TSAandFSAParallel as TSAandFSAParallel
import time
import logging
import PFSupport.GetElements as GetElements
from DSA.CheckFreeRun import CheckFreeRunStability_v1
import PFSupport.Utils as PFUtils

def RunDSA(app: pf.Application, dynModGrid: pf.DataObject, contingencyGrids: list[pf.DataObject], sTSAGenCCT: list,  sTSAGenMon: list, sSSSAGenMon: list, sFSAGenOut: list, sFSAGenMon: list, sFSALodLFDD: list, HGrids: list[pf.DataObject], AlgorithmSettings: tuple[int, int, int], ParallelAlgorithmSetting: int = 0, MainDirSaveFlag: int = 0):
    '''
    This is the main function that runs dynamic security assessment(DSA) of a project currently active in powerfactory.\n
    The dynamic stability of three types of stabilities is assessed, namely Transient stability(TS), small signal stability(SSS) and frequency stability(FS).\n
    The files in which the results are stored and the parameters for each type of stability is set inside this function localy.\n

    The Arguments of the function are:\n
    app - the powerfactory application in which the desired project should already be activated.\n
    dynModGrid - the grid in which the dynamic models used for DSA are temporarily stored.\n
    contingencyGrids - a list of grids in which contingencies should be considered.\n
    sTSAGenCCT - the generators near which contingencies for TSA should be considered. \n
    sTSAGenMon - the generators whose rotor angles should be monitored.\n
    sFSAGenOut - the generators whose outage should be considered during FSA.\n
    sFSAGenMon - the generators whose speed should be monitored during FSA.\n
    sFSALodLFDD - the loads that should be considered for LFDD when running FSA.\n
    HGrid - A list of grids to be considered when calculating rotational kinetic energy (Wk) and inerital constants (H)
    AlgorithmSettings - A tuple whise entrys define the algorithms used for stability analysis.\n
    ParallelAlgorithmSetting - An integer that determines what kind of parallel algorith to use.\n
    MainDirSaveFlag - A flag that determines the type of main result file export.
    '''
    assert(type(app) == pf.Application), "Argument 'app' is not of type powerfactory.Application"
    assert(type(dynModGrid) == pf.DataObject), "Argument 'dynModGrid' is not of type powerfactory.DataObject"
    assert(dynModGrid.GetClassName() == "ElmNet"), "Argument 'dynModGrid' is not of class 'ElmNet'"
    assert(type(contingencyGrids) == list), "Argument 'contigencyGrids' is not of type list"
    for i, val in enumerate(contingencyGrids):
        assert(type(val) == pf.DataObject), "Argument 'contingencyGrids["+str(i)+"]' is not of type powerfactory.DataObject"
        assert(val.GetClassName() == "ElmNet"), "Argument 'contingencyGrids["+str(i)+"]' is not of class 'ElmNet'"
    assert(type(sTSAGenCCT) == list), "Argument 'sTSAGenCCT' is not of type list"
    for i in range(len(sTSAGenCCT)):
        assert(type(sTSAGenCCT[i]) == pf.DataObject), "Argument sTSAGenCCT ["+str(i)+"] is not of type powerfactory.DataObject"
        assert(sTSAGenCCT[i].GetClassName() == "ElmSym"), "Argument sTSAGenCCT ["+str(i)+"] is not of class 'ElmSym'"
    assert(type(sTSAGenMon) == list), "Argument 'sTSAGenMon' is not of type list"
    for i in range(len(sTSAGenMon)):
        assert(type(sTSAGenMon[i]) == pf.DataObject), "Argument sTSAGenMon ["+str(i)+"] is not of type powerfactory.DataObject"
        assert(sTSAGenMon[i].GetClassName() == "ElmSym"), "Argument sTSAGenMon ["+str(i)+"] is not of class 'ElmSym'"
    assert(type(sFSAGenOut) == list), "Argument 'sFSAGenOut' is not of type list"
    for i in range(len(sSSSAGenMon)):
        assert(type(sSSSAGenMon[i]) == pf.DataObject), "Argument sSSSAGenMon ["+str(i)+"] is not of type powerfactory.DataObject"
        assert(sSSSAGenMon[i].GetClassName() == "ElmSym"), "Argument sSSSAGenMon ["+str(i)+"] is not of class 'ElmSym'"
    assert(type(sFSAGenOut) == list), "Argument 'sFSAGenOut' is not of type list"
    for i in range(len(sFSAGenOut)):
        assert(type(sFSAGenOut[i]) == pf.DataObject), "Argument sFSAGenOut ["+str(i)+"] is not of type powerfactory.DataObject"
        assert(sFSAGenOut[i].GetClassName() == "ElmSym"), "Argument sFSAGenOut ["+str(i)+"] is not of class 'ElmSym'"
    assert(type(sFSAGenMon) == list), "Argument 'sFSAGenMon' is not of type list"
    for i in range(len(sFSAGenMon)):
        assert(type(sFSAGenMon[i]) == pf.DataObject), "Argument sFSAGenMon ["+str(i)+"] is not of type powerfactory.DataObject"
        assert(sFSAGenMon[i].GetClassName() == "ElmSym"), "Argument sFSAGenMon ["+str(i)+"] is not of class 'ElmSym'"
    assert(type(sFSALodLFDD) == list), "Argument 'sFSALodLFDD' is not of type list"
    for i in range(len(sFSALodLFDD)):
        assert(type(sFSALodLFDD[i]) == pf.DataObject), "Argument sFSALodLFDD ["+str(i)+"] is not of type powerfactory.DataObject"
        assert(sFSALodLFDD[i].GetClassName() == "ElmLod"), "Argument sFSALodLFDD ["+str(i)+"] is not of class 'ElmLod'"
    for i, CurrGrid in enumerate(HGrids):
        assert(type(CurrGrid) == pf.DataObject), "Given argument 'InertiaGrid["+str(i)+"]' is not of type PowerFactory.DataObject"
        assert(CurrGrid.GetClassName() == "ElmNet"), "Given argument 'InertiaGrid["+str(i)+"]' is not of class 'ElmNet'"
    assert(type(AlgorithmSettings) == tuple), "Argument 'AlgorithmSettins' is not of type tuple"
    for i, entry in enumerate(AlgorithmSettings):
        assert(type(entry) == int), "Argument 'AlgorithmSettings["+str(i)+"] is not of type int."
        if i == 0:
            assert(entry in [0,1,2,3,4,5]), "Argument 'AlgorithmSettings[0]' must be either 0, 1, 2, 3, 4, or 5"
        if i == 1:
            assert(entry in [0,1,2]), "Argument 'AlgorithmSettings[1]' must be either 0, 1 or 2."
        if i == 2:
            assert(entry in [0]), "Argument 'AlgorithmSettings[2]' must be 0."
    assert(type(ParallelAlgorithmSetting) == int ), "Argument 'ParallelAlgorithmSetting' must be of type intiger."
    assert(ParallelAlgorithmSetting in [0,1]), "Argument 'ParalllelAlgorithmsetting' must be either 0 or 1."
    assert(MainDirSaveFlag in [0,1]), "Argument 'MainDirSaveFlag' must be either 0 or 1."
    #--------------------------------------------------------------------------------------------------
    # files

    #temporary csv files
    temp_LF = os.getenv("Temp_LF")
    temp_TSA = os.getenv("Temp_TSA")
    temp_SSSA = os.getenv("Temp_SSSA")
    temp_FSA = os.getenv("Temp_FSA")

    #temporary SSSA files
    pf_temp_SSSA = os.getcwd()+"\\"+os.getenv("Pf_temp_SSSA_file")

    #main files
    main_dir_LF = os.getenv("Main_dir_LF")          #used if MainDirSaveFlag = 1
    main_dir_TSA = os.getenv("Main_dir_TSA")        #used if MainDirSaveFlag = 1
    main_dir_SSSA = os.getenv("Main_dir_SSSA")      #used if MainDirSaveFlag = 1
    main_dir_FSA = os.getenv("Main_dir_FSA")        #used if MainDirSaveFlag = 1
    main_LF = os.getenv("Main_LF")                  #used if MainDirSaveFlag = 0
    main_TSA = os.getenv("Main_TSA")                #used if MainDirSaveFlag = 0
    main_SSSA = os.getenv("Main_SSSA")              #used if MainDirSaveFlag = 0  
    main_FSA = os.getenv("Main_FSA")                #used if MainDirSaveFlag = 0
    #------------------------------------------------
    # Freerun parameters 
    Freerun_cutoff_threshold = 0.001 # speed in pu
    max_n_of_increasing_oscillations = 30
    tStartFreeRun = -0.1
    tStopFreeRun = 50
    tSimStepFreeRun = 0.01
    FreeRunSettings = (Freerun_cutoff_threshold, max_n_of_increasing_oscillations, tStartFreeRun, tStopFreeRun, tSimStepFreeRun)
    #------------------------------------------------
    # Transient stability assessment
    #TSA parameters
    tStartTSA = -0.1
    tStopTSA = 2
    tSimStepTSA = 0.01
    tMaxClear = 1.99
    tMinClear = 0.1
    tStepTSA = 0.01
    CCT_treshold = 0.6
    nRecord = 5
    match AlgorithmSettings[0]:
        case 0:
            TSA_settings = (tStartTSA, tStopTSA, tSimStepTSA, tMaxClear, tMinClear, tStepTSA)
        case 1:
            TSA_settings = (tStartTSA, tStopTSA, tSimStepTSA, tMaxClear, tMinClear, tStepTSA)
        case 2:
            TSA_settings = (tStartTSA, tStopTSA, tSimStepTSA, tMaxClear, tMinClear, tStepTSA,CCT_treshold)
        case 3:
            TSA_settings = (tStartTSA, tStopTSA, tSimStepTSA, tMaxClear, tMinClear, tStepTSA)
        case 4:
            TSA_settings = (tStartTSA, tStopTSA, tSimStepTSA, tMaxClear, tMinClear, tStepTSA, CCT_treshold,nRecord)
        case 5:
            TSA_settings = (tStartTSA, tStopTSA, tSimStepTSA, tMaxClear, tMinClear, tStepTSA)

    #------------------------------------------------
    # Frequency stability assessment
    #FSA parameters
    #variables for simulaiton
    tStartFSA = -0.1
    tStopFSA = 50
    tSimStepFSA = 0.01

    #LFDD (UFLS) settings
    considerLFDD = False
    LFDDFreq = (0.98, 0.976, 0.972, 0.968, 0.964, 0.960)
    LFDDPow = (-8,-8,-8,-8,-8,-8)

    #M borders
    Mlim = (0.99, 0.97, 0.95)

    # RoCoF calc windows
    RoCoFCalcWindows = (0, 0.5)
    match AlgorithmSettings[1]:
        case 0 | 1:
            FSAsettings = (tStartFSA, tStopFSA, tSimStepFSA, considerLFDD, LFDDFreq, LFDDPow, Mlim)
        case 2:    
            FSAsettings = (tStartFSA, tStopFSA, tSimStepFSA, considerLFDD, LFDDFreq, LFDDPow, RoCoFCalcWindows)

    # H calc grid
    HGrids = HGrids

    #------------------------------------------------
    # Small signal stability assessment
    #SSSA parameters

    saveLeftEV = 0          # 0 - don't save, 1 - save, other values not permittable
    saveRightEV = 1         # 0 - don't save, 1 - save, other values not permittable
    saveParticFact = 1      # 0 - don't save, 1 - save, other values not permittable
    minReal = -10
    maxReal = 10
    minDampFreq = 0.5
    maxDampFreq = 3
    maxRelDamping = 10
    EV_par_settings = [saveLeftEV, saveRightEV, saveParticFact]
    SSSAsettings = EV_par_settings + [minReal, maxReal, minDampFreq, maxDampFreq, maxRelDamping]

    #------------------------------------------------
    #admin params
    iprint = False
    export = True

    # -------------------------------------------------------------------------------------------------
    #code
    # set consider reactive power limits for proper working of simulations
    oComLF = app.GetFromStudyCase("ComLdf")
    oComLF.SetAttribute("iopt_lim",1)


    #check if main files exist-----------------------
    if MainDirSaveFlag == 0:
        if not HandleFiles.CheckForSameRows(main_LF, main_TSA, main_SSSA, main_FSA):
            print("Stopping program.")
            logging.info("Stopping program.")
            sys.exit(3)

    time_initialise = time.time()
    #------------------------------------------------
    # Loadflow
    print("-------------------------------------------------------------------------------------------")
    logging.info("-------------------------------------------------------------------------------------------")
    print("Running loadflow.")
    logging.info("Running loadflow.")
    oLdfflag = oComLF.Execute()
    if oLdfflag != 0:
        print("Loadflow did not converge. Stopping program.")
        logging.info("Loadflow did not converge. Stopping program.")
        sys.exit(4)
    if export:
        HandleFiles.CreateTempCsvLFSLO(app, temp_LF)
    print("Loadflow run successful.")
    logging.info("Loadflow run successful.")
    time_loadflow = time.time()
    #------------------------------------------------
    # FreeRunStabilitycheck
    print("-------------------------------------------------------------------------------------------")
    logging.info("-------------------------------------------------------------------------------------------")
    print("Checking stability without contingencies.")
    logging.info("Checking stability without contingencies.")
    FreeRunFlag = CheckFreeRunStability_v1(app, dynModGrid, FreeRunSettings)
    if FreeRunFlag:
        print("System is stable without any inflicted contingencies.")
        logging.info("System is stable without any inflicted contingencies.")
    else:
        print("System is unstable without any inflicted contingencies. Stopping program.")
        logging.info("System is unstable without any inflicted contingencies. Stopping program.")
        sys.exit(5)
    time_FreeRunStabilityCheck = time.time()

    match ParallelAlgorithmSetting:
        case 0:
            #------------------------------------------------
            # TSA
            print("-------------------------------------------------------------------------------------------")
            logging.info("-------------------------------------------------------------------------------------------")
            print("Running TSA.")
            logging.info("Running TSA.")

            match AlgorithmSettings[0]:
                ## sequential functions
                case 0:
                    CCTs = TSA.TSAForTermAtGen(app, TSA_settings, dynModGrid, sTSAGenCCT, sTSAGenMon, iprint)
                case 1:
                    CCTs = TSA.TSAForTermAtGenAndLnes(app, TSA_settings, dynModGrid, contingencyGrids, sTSAGenCCT, sTSAGenMon, iprint)
                case 2:
                    CCTs = TSA.TSAUntilTreshold(app, TSA_settings, dynModGrid, contingencyGrids, sTSAGenCCT, sTSAGenMon, iprint)

                ## parallel funcitons
                case 3: 
                    CCTs = TSA.TSAForTermAtGenParallel(app, TSA_settings, dynModGrid, sTSAGenCCT, sTSAGenMon, iprint)
                case 4:
                    CCTs = TSA.TSAUntilTresholdParallel(app, TSA_settings, dynModGrid, contingencyGrids, sTSAGenCCT, sTSAGenMon, iprint)
                case 5:
                    CCTs = TSA.TSAForLinesParallel(app, TSA_settings, dynModGrid, sTSAGenCCT, sTSAGenMon, iprint)
            # writing temp TSA csv
            if export:
                HandleFiles.CreateTempCsvTSA(temp_TSA, CCTs)
            print("TSA run sucessful.")
            logging.info("TSA run sucessful.")
            time_TSA = time.time()

            #------------------------------------------------
            # FSA
            print("-------------------------------------------------------------------------------------------")
            logging.info("-------------------------------------------------------------------------------------------")
            print("Running FSA.")
            logging.info("Running FSA.")

            Hdata = FSA.CalculateInertia(app, HGrids)

            match AlgorithmSettings[1]:
                case 0:
                    FSA_data = FSA.FSA(app, FSAsettings, dynModGrid, sFSAGenOut, sFSAGenMon, sFSALodLFDD, iprint)
                case 1:
                    FSA_data = FSA.FSAParallel(app, FSAsettings, dynModGrid, sFSAGenOut, sFSAGenMon, sFSALodLFDD, iprint)
                case 2:
                    FSA_data = FSA.FSAParallel2(app, FSAsettings, dynModGrid, sFSAGenOut, sFSAGenMon, sFSALodLFDD, iprint)
            if export:
                match AlgorithmSettings[1]:
                    case 0 | 1:
                        HandleFiles.CreateTempCsvFSA(temp_FSA, FSA_data, Mlim, Hdata)
                    case 2:
                        HandleFiles.CreateTempCsvFSA2(temp_FSA, FSA_data, RoCoFCalcWindows, Hdata)
            print("FSA run sucessful.")
            logging.info("FSA run sucessful.")           
            time_FSA = time.time()

        case 1:
            print("-------------------------------------------------------------------------------------------")
            logging.info("-------------------------------------------------------------------------------------------")
            print("Running TSA and FSA.")
            logging.info("Running TSA and FSA.")
            Hdata = FSA.CalculateInertia(app, HGrids)
            TSAinfo = (TSA_settings, sTSAGenCCT, sTSAGenMon, contingencyGrids)
            FSAinfo = (FSAsettings, sFSAGenOut, sFSAGenMon, sFSALodLFDD)
            CCTs, FSA_data = TSAandFSAParallel.FullParallel(app, dynModGrid, TSAinfo, FSAinfo, AlgorithmSettings, iprint)
            if export:
                HandleFiles.CreateTempCsvTSA(temp_TSA, CCTs)
            if export:
                HandleFiles.CreateTempCsvFSA(temp_FSA, FSA_data, Mlim, Hdata)
            print("TSA and FSA run successful.")
            logging.info("TSA and FSA run successful.")
            time_TSA_and_FSA = time.time()

    #------------------------------------------------
    # SSSA
    print("-------------------------------------------------------------------------------------------")
    logging.info("-------------------------------------------------------------------------------------------")
    print("Running SSSA.")
    logging.info("Running SSSA.")
    match AlgorithmSettings[2]:
        case 0:
            Gen_record_SSSA = SSSA.SSSANormal(app, sSSSAGenMon, SSSAsettings, pf_temp_SSSA)
    if export:
        # HandleFiles.CreateTempCsvSSSA(pf_temp_SSSA, temp_SSSA, Gen_record_SSSA) This is incomplete legacy code and should not be used
        HandleFiles.CreateTempCsvSSSAv2(pf_temp_SSSA, temp_SSSA, Gen_record_SSSA, EV_par_settings)
    print("SSSA run sucessful.")
    logging.info("SSSA run sucessful.")
    time_SSSA = time.time()

    #------------------------------------------------
    #export temp files to main file    
    IsEmptyList = []
    if export:
        print("-------------------------------------------------------------------------------------------")
        logging.info("-------------------------------------------------------------------------------------------")
        print("Moving files from temporary directories to main directories.")
        logging.info("Moving files from temporary directories to main directories.")
        match MainDirSaveFlag:
        
            case 0: 
                #check if files are empty
                IsEmptyList.append(HandleFiles.CheckIfCsvEmpty(temp_LF))
                IsEmptyList.append(HandleFiles.CheckIfCsvEmpty(temp_TSA))
                IsEmptyList.append(HandleFiles.CheckIfCsvEmpty(temp_SSSA))
                IsEmptyList.append(HandleFiles.CheckIfCsvEmpty(temp_FSA))

                if not True in IsEmptyList:
                    HandleFiles.AppendTempCsvToMainCsv(temp_LF, main_LF)
                    HandleFiles.AppendTempCsvToMainCsv(temp_TSA, main_TSA)
                    HandleFiles.AppendTempCsvToMainCsv(temp_SSSA, main_SSSA)
                    HandleFiles.AppendTempCsvToMainCsv(temp_FSA, main_FSA)
                else:
                    print("One of the Temp Files was empty. Not exporting files.")
                    logging.warning("One of the Temp Files was empty. Not exporting files.")
            
            case 1:
                LF_file_name = f"LF.csv"
                HandleFiles.MoveTempCsvToMainDir(temp_LF, main_dir_LF, LF_file_name)
                TSA_file_name = f"TSA.csv"
                HandleFiles.MoveTempCsvToMainDir(temp_TSA, main_dir_TSA, TSA_file_name)
                SSSA_file_name = f"SSSA.csv"
                HandleFiles.MoveTempCsvToMainDir(temp_SSSA, main_dir_SSSA, SSSA_file_name)
                FSA_file_name = f"FSA.csv"
                HandleFiles.MoveTempCsvToMainDir(temp_FSA, main_dir_FSA, FSA_file_name)
    time_export = time.time()
    match ParallelAlgorithmSetting:
        case 0:
            time_list = [time_initialise, time_loadflow, time_FreeRunStabilityCheck, time_TSA, time_FSA, time_SSSA, time_export]
        case 1:
            time_list = [time_initialise, time_loadflow, time_FreeRunStabilityCheck, time_TSA_and_FSA, time_SSSA, time_export]
    return (time_list, TSA_settings, FSAsettings, SSSAsettings)