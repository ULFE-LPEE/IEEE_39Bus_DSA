'''
Author: Matjaz Skrlec
date: 11. 06. 2025
version: 1.0
description: This module is used for concurrent parallel execution of frequency stability assessment and transient Stability assessment.
'''
import os
import sys
from dotenv import load_dotenv
import DSA.OutOfStep as OutOfStep
import DSA.HandleFiles as HandleFiles
import DSA.LFDD as LFDD
import DSA.FSA as FSA
import DSA.TSA as TSA
import logging
import PFSupport.GetElements as GetElements
import time
import PFSupport.EnableDisableElements as EnableDisableElements
import json
load_dotenv()
sys.path.append(os.getenv("PowerfactoryPyFilePath"))
import powerfactory as pf


# support functions
def ExtractForName(ForName: str):
    forIndex = ForName.find(":")
    if forIndex:
        ForName = ForName[forIndex+1:]
    return ForName

def getForOrLocName(oElm) -> str:
    match type(oElm):
        case pf.DataObject: 
            if oElm.GetAttribute("for_name"):
                oElmName = oElm.GetAttribute("for_name")
                oElmName = ExtractForName(oElmName)
                return oElmName
            else:
                return oElm.GetAttribute("loc_name")
        case int:
            return(oElm)

def GetdtUnitModifier(oComInc):
    UnitDict = {"as": 1e18,
                "fs": 1e15,
                "ps": 1e12,
                "ns": 1e9,
                "us": 1e6,
                "ms": 1e3,
                "s": 1,
                "ks": 1e-3,
                "Ms": 1e-6,
                "Gs": 1e-9,
                "Ts": 1e-12,
                "Ps": 1e-15,
                "Es": 1e-18}
    dtUnit = oComInc.GetAttributeUnit('dtgrd')
    return(UnitDict[dtUnit])

def SetCurrVenvInScript(script_path, iprint:bool) -> bool:
    venv_path = sys.prefix
    if iprint:
        if sys.prefix == sys.base_prefix:
            print("You're currently working in system python")
            logging.info("You're currently working in system python")
        else:
            print("Passing venv to script")
            logging.info("Passing venv to script")
    package_path = os.path.join(venv_path,"Lib\\site-packages")
    venv_line = "venv_path = '" + str(package_path).replace("\\","\\\\") +"'\n"
    with open(script_path, "r", encoding='utf-8') as f:
        lines = f.readlines()

    lines[3] = venv_line
    with open(script_path, "w", encoding='utf-8') as f:
        f.writelines(lines)

def setEventsFSA(oComInc: pf.DataObject) -> tuple[pf.DataObject, list[tuple[pf.DataObject, int]]]:
    '''
    This function disables all events setup previous to Frequency stability assessment and saves the previoud setups.
    It also creates a generator outage event.
    '''
    assert(type(oComInc) is pf.DataObject), "Argument 'oComInc' is not of type powerfactory.DataObject"
    assert(oComInc.GetClassName() == "ComInc"), "Argument 'oComInc' is not a initial conditions command"

    # put the original events out of service and store the original value of the event
    EvtInitSetup = []
    oEvent = oComInc.p_event
    sEvents = oEvent.GetContents()
    for oEvt in sEvents:
        EvtInitSetup.append((oEvt,oEvt.GetAttribute("outserv")))
        oEvt.SetAttribute("outserv", 1)

    # add gen outage
    oGenOutEvt = oEvent.CreateObject("EvtSwitch", "Generator_outage")

    oGenOutEvt.SetAttribute("outserv", 0)
    oGenOutEvt.SetAttribute("i_switch", 0)
    oGenOutEvt.SetAttribute("time", 1)

    return(oGenOutEvt, EvtInitSetup)

def CreateOperationScenario(app: pf.DataObject, DynFoldersDisable: list[pf.DataObject], OperationScenarioName: str):
    CurrOperationScenario = app.GetActiveScenario()
    OperationScenarioFolder = app.GetProjectFolder("scen")
    if CurrOperationScenario:
        CurrOperationScenario.Deactivate()
        oOperationScenario = OperationScenarioFolder.AddCopy(CurrOperationScenario, OperationScenarioName)
    else:
        oOperationScenario = OperationScenarioFolder.CreateObject("IntScenario", OperationScenarioName)
    oOperationScenario.Activate()
    for Folder in DynFoldersDisable:
        for Elm in Folder.GetContents():
            match Elm.GetClassName():
                case "ElmComp":
                    Elm.SetAttribute("outserv", 1)
                case "IntFolder":
                    for Elm2 in Elm.GetContents():
                        Elm2.SetAttribute("outserv", 1)
    return CurrOperationScenario, oOperationScenario

def setupStudyCases(app: pf.Application, sGenCCT: list[pf.DataObject], ComElm_folder: pf.DataObject, studyCaseFolder: pf.DataObject, paraScriptPath: str, baseStudyCase: pf.DataObject, settings: list, DynFoldersDisable: list[pf.DataObject], iprint: bool) -> tuple[list[pf.DataObject], list[pf.DataObject]]:
    '''
    This function creates new study cases and ComPython objects for each generator in the list sGenCCT.

    The function takes the following arguments:\n
    :param app: Pwerfactory application object.\n
    :param sGenCCT: a list of generators for which to create study cases.\n
    :param ComElm_folder: The folder with the angle adder and out of step detection blocks.\n
    :param studyCaseFolder: the folder in which to create the study cases.\n
    :param paraScriptPath: the path to the parallelisation script.\n
    :param baseStudyCase: the base study case from which to create copies.\n
    :param settings: List of settings for dynamic simulation.\n
    :param DynFoldersDisable: List of folders that contain ComElm objects that are not to be considered during calculaiton.\n
    :param iprint: a boolean that determines if the results should be printed.\n
    '''
    assert(type(app) is pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(type(sGenCCT) is list), "The Argument 'sGenCCT' is not of type list"
    for i in range(len(sGenCCT)):
        assert(sGenCCT[i].GetClassName() == "ElmSym"), "The Argument 'sGenCCT["+str(i)+"] is not of class 'ElmSym'"
    assert(type(ComElm_folder) is pf.DataObject), "The Argument 'ComElm_folder' is not of type PowerFactory.DataObject."
    assert(type(studyCaseFolder) is pf.DataObject), "The Argument 'studyCaseFolder' is not of type 'Powerfactory.DataObject"
    assert(studyCaseFolder.GetClassName() == "IntPrjfolder"), "The Argument 'studyCaseFolder' is not of class 'IntPrjfolder'."
    assert(type(paraScriptPath) is str), "The Argument 'paraScriptPath' is not of type string."
    assert(os.path.isfile(paraScriptPath)), "The Argument 'paraScriptPath' is not a valid file path."
    assert(type(baseStudyCase) is pf.DataObject), "The Argument 'baseStudyCase' is not of type 'Powerfactory.DataObject"
    assert(baseStudyCase.GetClassName() == "IntCase"), "The Argument 'baseStudyCase' is not of class 'IntCase'."
    assert(type(settings) is tuple), "Given Argument 'settings' is not a tuple."
    assert(len(settings) == 6), "Given Argument 'settings' does not have 6 entrys as it should. The needed entrys are:\n\
                                - [0] The simulation start time (in s)\n\
                                - [1] The simulation stop time (in s)\n\
                                - [2] The simulation step time (in s)\n\
                                - [3] The maximum fault clearing time (in s)\n\
                                - [4]4The minimum fault clearing time (in s)\n\
                                - [5] The critical clearing time accuracy (in s)"
    assert(type(DynFoldersDisable) is list), "The Argument 'DynFoldersDisable' is not a list."
    for i, file in enumerate(DynFoldersDisable):
        assert(file.GetClassName() == "IntFolder"), "The Argument 'DynFoldersDisable["+str(i)+"]' is not of class 'IntFolder'."
    assert(type(iprint) is bool), "The Argument 'iprint' is not of type boolean."
    createdStudyCases: list[pf.DataObject] = []
    createdComPython: list[pf.DataObject] = []
    
    # Create operation scenario
    CurrOperationScenario, oOperationScenarioTSA = CreateOperationScenario(app, DynFoldersDisable, "OperationScenarioTSA")

    # Create new StudyCase for each generator in sGenCCT
    sGensAct = GetElements.GetElements(app, "ElmSym", ["outserv", 0])
    # sGens = GetElements.GetElements(app, "ElmSym", ["outserv", 0], num = 3, rand = True)
    EnableDisableElements.DisableElm(sGensAct, Attributes = [["pgini", 1],["qgini", 5]], mode = ['absmax', 'absmax'], andor = "and") # izključi Generatorje, če je nastavljena delovna moč po 1 MW in jalova moč pod 5Mvar
    sLodsAct = GetElements.GetElements(app, "ElmLod", ["outserv", 0])
    EnableDisableElements.DisableElm(sLodsAct, Attributes=[["plini",0],["qlini",0]], mode = ["eval", "eval"], andor = "and") # izključi bremena, ki imajo nastavljeno moč na 0MW in jalovo moč na 0Mvar
    for i, generator in enumerate(sGenCCT):
        studyCaseName = f'SC at generator {generator.GetAttribute("loc_name")}'

        # Create new study case from the base study case
        newStudyCase = studyCaseFolder.AddCopy(baseStudyCase)
        newStudyCase.SetAttribute("loc_name", f"{studyCaseName}")
        if newStudyCase is not None:
            if iprint:
                print(f"Created study case: {newStudyCase.GetAttribute('loc_name')}")
                logging.info(f"Created study case: {newStudyCase.GetAttribute('loc_name')}")
            createdStudyCases.append(newStudyCase)
        else:
            raise ValueError(f"Failed to create study case for {studyCaseName}.")

        # Create a new ComPython for the study case
        comPythonObject = newStudyCase.CreateObject("ComPython", "Python Skripta TSA")
        comPythonObject.SetAttribute("filePath", paraScriptPath)

        # Define it's external objects
        DefineInput(comPythonObject, ComElm_folder, sGenCCT[i], settings)
        createdComPython.append(comPythonObject)

    # reactivate base study case and deactivate operation scenario
    
    oOperationScenarioTSA.Save()
    baseStudyCase.Activate()
    oOperationScenarioTSA.Deactivate()
    if CurrOperationScenario:
        CurrOperationScenario.Activate()
    
    return createdStudyCases, createdComPython

def setInitialParamsFSA(oComInc: pf.DataObject, oComSim: pf.DataObject, SimInitSetup: tuple[int, int, float, float, float, int]) -> None:
    '''
    This function sets the initial parameters of the simulation during frequency stability assessment.
    '''

    assert(type(oComInc) is pf.DataObject), "Argument 'oComInc' is not of type powerfactory.DataObject"
    assert(oComInc.GetClassName() == "ComInc"), "Argument 'oComInc' is not a initial conditions command"
    assert(type(oComSim) is pf.DataObject), "Argument 'oComSim' is not of type powerfactory.DataObject"
    assert(oComSim.GetClassName() == "ComSim"), "Argument 'oComsim' is not a simulation command"

    assert(type(SimInitSetup) is tuple), "Argument 'SimInitSetup' is not of type tuple"
    assert(len(SimInitSetup) == 6), "Argument 'SimInitsetup' does not have 5 entrys"

    assert(type(SimInitSetup[0]) is int), "Argument 'SimInitSetup[0]' is not ot type int"
    assert(type(SimInitSetup[1]) is int), "Argument 'SimInitSetup[1]' is not ot type int"
    assert(type(SimInitSetup[2]) in [int, float]), "Argument 'SimInitSetup[2]' is not of type int or float"
    assert(type(SimInitSetup[3]) in [int, float]), "Argument 'SimInitSetup[3]' is not of type int or float"
    assert(type(SimInitSetup[4]) in [int, float]), "Argument 'SimInitSetup[4]' is not of type int or float"

    oComInc.iopt_simscn = SimInitSetup[0]
    oComInc.iopt_sample = SimInitSetup[1]
    oComInc.tstart = SimInitSetup[2]
    oComSim.tstop = SimInitSetup[3]
    oComInc.dtgrd = SimInitSetup[4]
    oComInc.automaticCompilation = SimInitSetup[5]

def setInitialEventsFSA(oGenOutEvt: pf.DataObject, initUserEvents: tuple[pf.DataObject, list[tuple[pf.DataObject, int]]]) -> bool:
    '''
    This function set up the initial events as they were before the frequency stability assessment
    '''
    assert(type(oGenOutEvt) is pf.DataObject), "Argument 'oGetOutEvt' is not of type powerfactory.DataObject"
    assert(oGenOutEvt.GetClassName() == "EvtSwitch"), "Argument 'oGenOutEvt' is not of class 'EvtSwitch'"
    assert(type(initUserEvents) is list), "Argument 'initUserEvents' is not of type list"

    oGenOutEvt.Delete()

    for oEvt in initUserEvents:
        oEvt[0].SetAttribute("outserv", oEvt[1])

    return (True)

def ReadResFilesTSA(sGenCCT: list[pf.DataObject], tempResultsDir: str, ) -> list[list]:
    CCT_info_lists: list[list] = []
    for id, generator in enumerate(sGenCCT):
        generatorName = getForOrLocName(generator)
        if ":" in generatorName:
            index = generatorName.find(":")
            generatorName = generatorName[index+1:]
        file_indexing = 0
        tempFilePath = f"{tempResultsDir}\\cctInfo_{generatorName}_{file_indexing}.pkl"
        while os.path.exists(tempFilePath):
            try:
                cctResults = HandleFiles.loadResultsFromTemporaryFile(tempFilePath)
                if cctResults is not None:
                    CCT_info_lists.append(cctResults)
                else:
                    # This case might occur if the file exists but is empty or corrupted in a way that load returns None
                    print(f"Loaded results are None for generator {generatorName} from {tempFilePath}.")
                    logging.warning(f"Loaded results are None for generator {generatorName} from {tempFilePath}.")
            except FileNotFoundError:
                print(f"Temporary results file not found for generator {generatorName}: {tempFilePath}")
                logging.error(f"Temporary results file not found for generator {generatorName}: {tempFilePath}")
            except Exception as e: # Catch other potential errors during loading (e.g., pickle errors)
                print(f"Failed to load results for generator {generatorName} from {tempFilePath}. Error: {e}")
                logging.error(f"Failed to load results for generator {generatorName} from {tempFilePath}. Error: {e}")
            file_indexing = file_indexing + 1
            tempFilePath = f"{tempResultsDir}\\cctInfo_{generatorName}_{file_indexing}.pkl"
    return(CCT_info_lists)

def RedefineToOriginalElementsTSA(app: pf.Application, CCT_info_lists: list[list]) -> list[list]:
    for index, CCT_info_list in enumerate(CCT_info_lists):
        original_term_ref = CCT_info_list[1]
        original_crit_gen_ref = CCT_info_list[2]
        original_fault_elm_ref = CCT_info_list[4]

        try:
            # Try to get the terminal object
            term_objects = app.GetCalcRelevantObjects(f"*{original_term_ref}")
            if term_objects: # Check if the list is not empty
                CCT_info_list[1] = term_objects[0]
                CCT_info_lists[index][1] = term_objects[0]
            else:
                logging.warning(f"Could not find object for reference: {original_term_ref}. Keeping original reference.")
        except Exception as e:
            logging.error(f"Error getting object for reference {original_term_ref}: {e}. Keeping original reference.")

        try:
            # Try to get the critical generator object
            crit_gen_objects = app.GetCalcRelevantObjects(f"*{original_crit_gen_ref}")
            if crit_gen_objects: # Check if the list is not empty
                CCT_info_list[2] = crit_gen_objects[0]
                CCT_info_lists[index][2] = crit_gen_objects[0]
            else:
                logging.warning(f"Could not find object for reference: {original_crit_gen_ref}. Keeping original reference.")
        except Exception as e:
            logging.error(f"Error getting object for reference {original_crit_gen_ref}: {e}. Keeping original reference.")

        try:
            # Try to get the fault element object
            fault_elm_objects = app.GetCalcRelevantObjects(f"*{original_fault_elm_ref}")
            if fault_elm_objects: # Check if the list is not empty
                CCT_info_list[4] = fault_elm_objects[0]
                CCT_info_lists[index][4] = fault_elm_objects[0]
            else:
                logging.warning(f"Could not find object for reference: {original_fault_elm_ref}. Keeping original reference.")
        except Exception as e:
            logging.error(f"Error getting object for reference {original_fault_elm_ref}: {e}. Keeping original reference.")

    return CCT_info_lists

def ReadResFilesFSA(sGenOut: list[pf.DataObject], tempResultsDir: str, ) -> list[list]:
    FSA_data_lists: list[list] = []
    for id, generator in enumerate(sGenOut):
        generatorName = getForOrLocName(generator)
        if ":" in generatorName:
            index = generatorName.find(":")
            generatorName = generatorName[index+1:]
        file_indexing = 0
        tempFilePath = f"{tempResultsDir}\\FSAdata_{generatorName}_{file_indexing}.pkl"
        while os.path.exists(tempFilePath):
            try:
                FSAResults = HandleFiles.loadResultsFromTemporaryFile(tempFilePath)
                if FSAResults is not None:
                    FSA_data_lists.append(FSAResults)
                else:
                    # This case might occur if the file exists but is empty or corrupted in a way that load returns None
                    print(f"Loaded results are None for generator {generatorName} from {tempFilePath}.")
                    logging.warning(f"Loaded results are None for generator {generatorName} from {tempFilePath}.")
            except FileNotFoundError:
                print(f"Temporary results file not found for generator {generatorName}: {tempFilePath}")
                logging.error(f"Temporary results file not found for generator {generatorName}: {tempFilePath}")
            except Exception as e: # Catch other potential errors during loading (e.g., pickle errors)
                print(f"Failed to load results for generator {generatorName} from {tempFilePath}. Error: {e}")
                logging.error(f"Failed to load results for generator {generatorName} from {tempFilePath}. Error: {e}")
            file_indexing = file_indexing + 1
            tempFilePath = f"{tempResultsDir}\\FSAdata_{generatorName}_{file_indexing}.pkl"
    
    return(FSA_data_lists)

def RedefineToOriginalElementsTSATreshold(app: pf.Application, whole_CCT_info_lists: list[list]) -> list[list]:
    for CCT_info_lists in whole_CCT_info_lists:
        for index, CCT_info_list in enumerate(CCT_info_lists):
            original_term_ref = CCT_info_list[1]
            original_crit_gen_ref = CCT_info_list[2]
            original_fault_elm_ref = CCT_info_list[4]

            try:
                # Try to get the terminal object
                term_objects = app.GetCalcRelevantObjects(f"*{original_term_ref}")
                if term_objects: # Check if the list is not empty
                    CCT_info_list[1] = term_objects[0]
                    CCT_info_lists[index][1] = term_objects[0]
                else:
                    logging.warning(f"Could not find object for reference: {original_term_ref}. Keeping original reference.")
            except Exception as e:
                logging.error(f"Error getting object for reference {original_term_ref}: {e}. Keeping original reference.")

            try:
                # Try to get the critical generator object
                crit_gen_objects = app.GetCalcRelevantObjects(f"*{original_crit_gen_ref}")
                if crit_gen_objects: # Check if the list is not empty
                    CCT_info_list[2] = crit_gen_objects[0]
                    CCT_info_lists[index][2] = crit_gen_objects[0]
                else:
                    logging.warning(f"Could not find object for reference: {original_crit_gen_ref}. Keeping original reference.")
            except Exception as e:
                logging.error(f"Error getting object for reference {original_crit_gen_ref}: {e}. Keeping original reference.")

            try:
                # Try to get the fault element object
                fault_elm_objects = app.GetCalcRelevantObjects(f"*{original_fault_elm_ref}")
                if fault_elm_objects: # Check if the list is not empty
                    CCT_info_list[4] = fault_elm_objects[0]
                    CCT_info_lists[index][4] = fault_elm_objects[0]
                else:
                    logging.warning(f"Could not find object for reference: {original_fault_elm_ref}. Keeping original reference.")
            except Exception as e:
                logging.error(f"Error getting object for reference {original_fault_elm_ref}: {e}. Keeping original reference.")

    return whole_CCT_info_lists

def DefineInput(comPythonObject: pf.DataObject, ComElm_folder: pf.DataObject, oGen: pf.DataObject, settings: list) -> bool:
    ParamTypeInputList = ["double", "double", "double", "double", "double", "double"]
    ParamNameInputList = ["tStartTSA", "tStopTSA", "tSimStepTSA", "tMaxClear", "tMinClear" ,"tStepTSA"]
    ParamValueInputList = list(map(lambda x: str(x), settings))
    comPythonObject.SetAttribute("IntType", ParamTypeInputList)
    comPythonObject.SetAttribute("IntName", ParamNameInputList)
    comPythonObject.SetAttribute("IntExpr", ParamValueInputList)
    comPythonObject.obj_name = ["generatorInput", "ComElm_folder"] # type: ignore
    comPythonObject.obj_id = [oGen, ComElm_folder] # type: ignore
    # comPythonObject.obj_desc = [""] # type: ignore
    return (True)

def setupStudyCasesTSAUntilTreshold(app: pf.Application, sGenCCT: list[pf.DataObject], ComElm_folder: pf.DataObject, studyCaseFolder: pf.DataObject, paraScriptPath: str, baseStudyCase: pf.DataObject, settings: tuple, contingencyGrids, DynFoldersDisable: list[pf.DataObject], iprint: bool) -> tuple[list[pf.DataObject], list[pf.DataObject]]:
    '''
    This function creates new study cases and ComPython objects for each generator in the list sGenCCT.

    The function takes the following arguments:\n
    :param app: Pwerfactory application object.\n
    :param sGenCCT: a list of generators for which to create study cases.\n
    :param ComElm_folder: The folder with the angle adder and out of step detection blocks.\n
    :param studyCaseFolder: the folder in which to create the study cases.\n
    :param paraScriptPath: the path to the parallelisation script.\n
    :param baseStudyCase: the base study case from which to create copies.\n
    :param settings: List of settings for dynamic simulation.\n
    :param CCT_treshold: setting for when to stop searching for new elements to calculate CCTs.\n
    :param contingencyGrids: a list of grids in which contingencies should be considered.\n
    :param iprint: a boolean that determines if the results should be printed.\n
    '''
    assert(type(app) is pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(type(sGenCCT) is list), "The Argument 'sGenCCT' is not of type list"
    for i in range(len(sGenCCT)):
        assert(sGenCCT[i].GetClassName() == "ElmSym"), "The Argument 'sGenCCT["+str(i)+"] is not of class 'ElmSym'"
    assert(type(ComElm_folder) is pf.DataObject), "The Argument 'ComElm_folder' is not of type PowerFactory.DataObject."
    assert(type(studyCaseFolder) is pf.DataObject), "The Argument 'studyCaseFolder' is not of type 'Powerfactory.DataObject"
    assert(studyCaseFolder.GetClassName() == "IntPrjfolder"), "The Argument 'studyCaseFolder' is not of class 'IntPrjfolder'."
    assert(type(paraScriptPath) is str), "The Argument 'paraScriptPath' is not of type string."
    assert(os.path.isfile(paraScriptPath)), "The Argument 'paraScriptPath' is not a valid file path."
    assert(type(baseStudyCase) is pf.DataObject), "The Argument 'baseStudyCase' is not of type 'Powerfactory.DataObject"
    assert(baseStudyCase.GetClassName() == "IntCase"), "The Argument 'baseStudyCase' is not of class 'IntCase'."
    assert(type(settings) is tuple), "Given Argument 'settings' is not a list."
    assert(len(settings) == 8), "Given Argument 'settings' does not have 6 entrys as it should. The needed entrys are:\n\
                                - [0] The simulation start time (in s)\n\
                                - [1] The simulation stop time (in s)\n\
                                - [2] The simulation step time (in s)\n\
                                - [3] The maximum fault clearing time (in s)\n\
                                - [4] The minimum fault clearing time (in s)\n\
                                - [5] The critical clearing time accuracy (in s)\n\
                                - [6] The Threshold at which to stop searching for CCTs (in s)\n\
                                - [7] The number at which to stop coninue searching for further elements in grid."
    assert(type(contingencyGrids) is list), "Argument 'contigencyGrids' is not of type list"
    for i, val in enumerate(contingencyGrids):
        assert(type(val) is pf.DataObject), "Argument 'contingencyGrids["+str(i)+"]' is not of type powerfactory.DataObject"
        assert(val.GetClassName() == "ElmNet"), "Argument 'contingencyGrids["+str(i)+"]' is not of class 'ElmNet'"
    assert(type(iprint) is bool), "The Argument 'iprint' is not of type boolean."
    createdStudyCases: list[pf.DataObject] = []
    createdComPython: list[pf.DataObject] = []

    # Create operation scenario
    CurrOperationScenario, oOperationScenarioTSA = CreateOperationScenario(app, DynFoldersDisable, "OperationScenarioTSA")
    sGensAct = GetElements.GetElements(app, "ElmSym", ["outserv", 0])
    # sGens = GetElements.GetElements(app, "ElmSym", ["outserv", 0], num = 3, rand = True)
    EnableDisableElements.DisableElm(sGensAct, Attributes = [["pgini", 1],["qgini", 5]], mode = ['absmax', 'absmax'], andor = "and") # izključi Generatorje, če je nastavljena delovna moč po 1 MW in jalova moč pod 5Mvar
    sLodsAct = GetElements.GetElements(app, "ElmLod", ["outserv", 0])
    EnableDisableElements.DisableElm(sLodsAct, Attributes=[["plini",0],["qlini",0]], mode = ["eval", "eval"], andor = "and") # izključi bremena, ki imajo nastavljeno moč na 0MW in jalovo moč na 0Mvar
    # Create new StudyCase for each generator in sGenCCT
    for i, generator in enumerate(sGenCCT):
        studyCaseName = f'SC at generator {generator.GetAttribute("loc_name")}'

        # Create new study case from the base study case
        newStudyCase = studyCaseFolder.AddCopy(baseStudyCase)
        newStudyCase.SetAttribute("loc_name", f"{studyCaseName}")
        if newStudyCase is not None:
            if iprint:
                print(f"Created study case: {newStudyCase.GetAttribute('loc_name')}")
                logging.info(f"Created study case: {newStudyCase.GetAttribute('loc_name')}")
            createdStudyCases.append(newStudyCase)
        else:
            raise ValueError(f"Failed to create study case for {studyCaseName}.")

        # Create a new ComPython for the study case
        comPythonObject = newStudyCase.CreateObject("ComPython", "Python Skripta TSA")
        comPythonObject.SetAttribute("filePath", paraScriptPath)

        # Define it's external objects
        DefineInputTSAUntilTreshold(comPythonObject, ComElm_folder, sGenCCT[i], contingencyGrids, settings)
        createdComPython.append(comPythonObject)

    # reactivate base study case and deactivate operation scenario
    oOperationScenarioTSA.Save()
    baseStudyCase.Activate()
    oOperationScenarioTSA.Deactivate()
    if CurrOperationScenario:
        CurrOperationScenario.Activate()
    
    return createdStudyCases, createdComPython

def DefineInputTSAUntilTreshold(comPythonObject: pf.DataObject, ComElm_folder: pf.DataObject, oGen: pf.DataObject, contingencyGrids: list[pf.DataObject], settings: list) -> bool:
    ParamTypeInputList = ["double", "double", "double", "double", "double", "double", "double", "int"]
    ParamNameInputList = ["tStartTSA", "tStopTSA", "tSimStepTSA", "tMaxClear", "tMinClear" ,"tStepTSA", "CCT_treshold", "nRecord"]
    ParamValueInputList = list(map(lambda x: str(x), settings))
    comPythonObject.SetAttribute("IntType", ParamTypeInputList)
    comPythonObject.SetAttribute("IntName", ParamNameInputList)
    comPythonObject.SetAttribute("IntExpr", ParamValueInputList)
    contingencyGridsNameList = []
    contingencyGridsObjectList = []
    for i, obj in enumerate(contingencyGrids):
        contingencyGridsNameList.append(f"ContingencyGrid_{i}")
        contingencyGridsObjectList.append(obj)
    comPythonObject.obj_name = ["generatorInput", "ComElm_folder"]+contingencyGridsNameList # type: ignore
    comPythonObject.obj_id = [oGen, ComElm_folder]+contingencyGridsObjectList # type: ignore
    # comPythonObject.obj_desc = [""] # type: ignore

def setUserParamasFSA(oComInc: pf.DataObject, oComSim: pf.DataObject, tStartFSA: float, tStopFSA: float, tSimStepFSA: float) -> tuple[int, int, float, float, float, int]:
    '''
    This function sets the parameters of the simulation during frequency stability assessment and returns the initial settings.
    '''

    assert(type(oComInc) is pf.DataObject), "Argument 'oComInc' is not of type powerfactory.DataObject"
    assert(oComInc.GetClassName() == "ComInc"), "Argument 'oComInc' is not a initial conditions command"
    assert(type(oComSim) is pf.DataObject), "Argument 'oComSim' is not of type powerfactory.DataObject"
    assert(oComSim.GetClassName() == "ComSim"), "Argument 'oComSim' is not a simulation command"

    assert(type(tStartFSA) in [int, float]), "Argument 'tStartFSA' is not of type int or float"
    assert(type(tStopFSA) in [int, float]), "Argument 'tStopFSA' is not of type int or float"
    assert(type(tSimStepFSA) in [int, float]), "Argument 'tSimStepFSA' is not of type int or float"

    assert(tStartFSA <= 0), "Simulation start time ('tStartFSA') should be lower or equal to 0"
    assert(tStopFSA > tStartFSA), "Simulation stop time ('tStopFSA') has to be higher than simulation start time"

    # get modifier for dt
    dtModifier = GetdtUnitModifier(oComInc)

    # Get initial simulation setup
    SimInitSetup = (oComInc.iopt_simscn, oComInc.iopt_sample, oComInc.tstart, oComSim.tstop, oComInc.dtgrd, oComInc.automaticCompilation)

    oComInc.iopt_simscn = 0
    oComInc.iopt_sample = 0
    oComInc.tstart = tStartFSA
    oComSim.tstop = tStopFSA
    oComInc.dtgrd = tSimStepFSA*dtModifier
    oComInc.automaticCompilation = 0

    return(SimInitSetup)

def setupStudyCasesFSA(app: pf.Application, sGenOut: list[pf.DataObject], MgridFolder: pf.DataObject, studyCaseFolder: pf.DataObject, paraScriptPath: str, baseStudyCase: pf.DataObject, M_settings: tuple[float], DynFoldersDisable: list[pf.DataObject], iprint: bool) -> tuple[list[pf.DataObject], list[pf.DataObject]]:
    '''
    This function creates new study cases and ComPython objects for each generator in the list sGenOut.

    The function takes the following arguments:\n
    :param app: Pwerfactory application object.\n
    :param sGenOut: a list of generators for which to create study cases.\n
    :param MgridFolder: The folder with the blocks that monitor output parameters.\n
    :param studyCaseFolder: the folder in which to create the study cases.\n
    :param paraScriptPath: the path to the parallelisation script.\n
    :param baseStudyCase: the base study case from which to create copies.\n
    :param settings: List of settings for dynamic simulation.\n
    :param iprint: a boolean that determines if the results should be printed.\n
    '''
    assert(type(app) is pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(type(sGenOut) is list), "The Argument 'sGenOut' is not of type list"
    for i in range(len(sGenOut)):
        assert(sGenOut[i].GetClassName() == "ElmSym"), "The Argument 'sGenOut["+str(i)+"] is not of class 'ElmSym'"
    assert(type(MgridFolder) is pf.DataObject), "The Argument 'MgridFolder' is not of type powerfactory.DataObject."
    assert(type(studyCaseFolder) is pf.DataObject), "The Argument 'studyCaseFolder' is not of type 'Powerfactory.DataObject"
    assert(studyCaseFolder.GetClassName() == "IntPrjfolder"), "The Argument 'studyCaseFolder' is not of class 'IntPrjfolder'."
    assert(type(paraScriptPath) is str), "The Argument 'paraScriptPath' is not of type string."
    assert(os.path.isfile(paraScriptPath)), "The Argument 'paraScriptPath' is not a valid file path."
    assert(type(baseStudyCase) is pf.DataObject), "The Argument 'baseStudyCase' is not of type 'Powerfactory.DataObject"
    assert(baseStudyCase.GetClassName() == "IntCase"), "The Argument 'baseStudyCase' is not of class 'IntCase'."
    assert(type(M_settings) is tuple), "Given Argument 'M_settings' is not a list."
    for i,M_set in enumerate(M_settings):
        assert(type(M_set) in [int, float]), "Given Argument 'M_settings["+str(i)+"] in not of class int or float"
    assert(type(iprint) is bool), "The Argument 'iprint' is not of type boolean."
    createdStudyCases: list[pf.DataObject] = []
    createdComPython: list[pf.DataObject] = []

    # Create operation scenario
    CurrOperationScenario, oOperationScenarioFSA = CreateOperationScenario(app, DynFoldersDisable, "OperationScenarioFSA")
    
    # Create new StudyCase for each generator in sGenCCT
    for i, generator in enumerate(sGenOut):
        studyCaseName = f'Generator {generator.GetAttribute("loc_name")} outage.'

        # Create new study case from the base study case
        newStudyCase = studyCaseFolder.AddCopy(baseStudyCase)
        newStudyCase.SetAttribute("loc_name", f"{studyCaseName}")
        if newStudyCase is not None:
            if iprint:
                print(f"Created study case: {newStudyCase.GetAttribute('loc_name')}")
                logging.info(f"Created study case: {newStudyCase.GetAttribute('loc_name')}")
            createdStudyCases.append(newStudyCase)
        else:
            raise ValueError(f"Failed to create study case for {studyCaseName}.")

        # Create a new ComPython for the study case
        comPythonObject = newStudyCase.CreateObject("ComPython", "Python Skripta FSA")
        comPythonObject.SetAttribute("filePath", paraScriptPath)

        # Define it's external objects

        DefineInputFSA(comPythonObject, MgridFolder, generator, M_settings)
        createdComPython.append(comPythonObject)
    
    # reactivate base study case and deactivate operation scenario
    oOperationScenarioFSA.Save()
    baseStudyCase.Activate()
    oOperationScenarioFSA.Deactivate()
    if CurrOperationScenario:
        CurrOperationScenario.Activate()
    
    return createdStudyCases, createdComPython

def DefineInputFSA(comPythonObject: pf.DataObject, ComElm_folder: pf.DataObject, oGen: pf.DataObject, M_settings: list) -> bool:
    ParamTypeInputList = ["double"]*len(M_settings)
    ParamNameInputList = []
    for i, M_set in enumerate(M_settings):
        ParamNameInputList.append(f'M_setting_{i}')
    ParamValueInputList = list(map(lambda x: str(x), M_settings))
    comPythonObject.SetAttribute("IntType", ParamTypeInputList)
    comPythonObject.SetAttribute("IntName", ParamNameInputList)
    comPythonObject.SetAttribute("IntExpr", ParamValueInputList)
    comPythonObject.obj_name = ["generatorInput", "ComElm_folder"] # type: ignore
    comPythonObject.obj_id = [oGen, ComElm_folder] # type: ignore
    # comPythonObject.obj_desc = [""] # type: ignore
    return (True)

def CleanupTempTSA(tempResultsDir: str) -> bool:
    filepaths = [os.path.join(tempResultsDir, filename) for filename in os.listdir(tempResultsDir)]
    for filepath in filepaths:
        if "cctInfo_" in filepath:
            try:
                os.remove(filepath)
            except FileNotFoundError:
                logging.warning(f"Temporary file not found during cleanup, skipping removal: {filepath}")
            except OSError as e:
                logging.error(f"Error removing temporary file {filepath}: {e}")
            except Exception as e:
                logging.error(f"Unexpected error removing temporary file {filepath}: {e}")
    return True

def CleanupTempFSA(tempResultsDir: str) -> bool:
    filepaths = [os.path.join(tempResultsDir, filename) for filename in os.listdir(tempResultsDir)]
    for filepath in filepaths:
        if "FSAdata_" in filepath:
            try:
                os.remove(filepath)
            except FileNotFoundError:
                logging.warning(f"Temporary file not found during cleanup, skipping removal: {filepath}")
            except OSError as e:
                logging.error(f"Error removing temporary file {filepath}: {e}")
            except Exception as e:
                logging.error(f"Unexpected error removing temporary file {filepath}: {e}")

    return True

def setupStudyCasesTSAForLines(app: pf.Application, sGenCCT: list[pf.DataObject], ComElm_folder: pf.DataObject, studyCaseFolder: pf.DataObject, paraScriptPath: str, baseStudyCase: pf.DataObject, settings: list, DynFoldersDisable: list[pf.DataObject], iprint: bool) -> tuple[list[pf.DataObject], list[pf.DataObject]]:
    '''
    This function creates new study cases and ComPython objects for each generator in the list sGenCCT.

    The function takes the following arguments:\n
    :param sGenCCT: a list of generators for which to create study cases.\n
    :param ComElm_folder: The folder with the angle adder and out of step detection blocks.\n
    :param studyCaseFolder: the folder in which to create the study cases.\n
    :param paraScriptPath: the path to the parallelisation script.\n
    :param baseStudyCase: the base study case from which to create copies.\n
    :param settings: Tuple of settings for dynamic simulation.\n
    :param CCT_treshold: setting for when to stop searching for new elements to calculate CCTs.\n
    :param contingencyGrids: a list of grids in which contingencies should be considered.\n
    :param iprint: a boolean that determines if the results should be printed.\n
    '''
    assert(type(sGenCCT) is list), "The Argument 'sGenCCT' is not of type list"
    for i in range(len(sGenCCT)):
        assert(sGenCCT[i].GetClassName() == "ElmSym"), "The Argument 'sGenCCT["+str(i)+"] is not of class 'ElmSym'"
    assert(type(ComElm_folder) is pf.DataObject), "The Argument 'ComElm_folder' is not of type PowerFactory.DataObject."
    assert(type(studyCaseFolder) is pf.DataObject), "The Argument 'studyCaseFolder' is not of type 'Powerfactory.DataObject"
    assert(studyCaseFolder.GetClassName() == "IntPrjfolder"), "The Argument 'studyCaseFolder' is not of class 'IntPrjfolder'."
    assert(type(paraScriptPath) is str), "The Argument 'paraScriptPath' is not of type string."
    assert(os.path.isfile(paraScriptPath)), "The Argument 'paraScriptPath' is not a valid file path."
    assert(type(baseStudyCase) is pf.DataObject), "The Argument 'baseStudyCase' is not of type 'Powerfactory.DataObject"
    assert(baseStudyCase.GetClassName() == "IntCase"), "The Argument 'baseStudyCase' is not of class 'IntCase'."
    assert(type(settings) is tuple), "Given Argument 'settings' is not a tuple."
    assert(len(settings) == 6), "Given Argument 'settings' does not have 6 entrys as it should. The needed entrys are:\n\
                                - [0] The simulation start time (in s)\n\
                                - [1] The simulation stop time (in s)\n\
                                - [2] The simulation step time (in s)\n\
                                - [3] The maximum fault clearing time (in s)\n\
                                - [4] The minimum fault clearing time (in s)\n\
                                - [5] The critical clearing time accuracy (in s)."
    assert(type(iprint) is bool), "The Argument 'iprint' is not of type boolean."

    createdStudyCases: list[pf.DataObject] = []
    createdComPython: list[pf.DataObject] = []

    # Get lines for Short circuit calculations
    sAllLinesForSc = []

    #Get bus near generator
    sSCTerms = TSA.getGenBus(sGenCCT)

    for oSCTerms in sSCTerms:
        #Get lines for calculations
        sLinesForSc= TSA.GetRelevantLines2(oSCTerms)
        sAllLinesForSc = sAllLinesForSc + sLinesForSc
    

    # Remove duplicates
    sAllLinesForSc = list(set(sAllLinesForSc))

    # Create operation scenario
    CurrOperationScenario, oOperationScenarioTSA = CreateOperationScenario(app, DynFoldersDisable, "OperationScenarioTSA")
    sGensAct = GetElements.GetElements(app, "ElmSym", ["outserv", 0])
    # sGens = GetElements.GetElements(app, "ElmSym", ["outserv", 0], num = 3, rand = True)
    EnableDisableElements.DisableElm(sGensAct, Attributes = [["pgini", 1],["qgini", 5]], mode = ['absmax', 'absmax'], andor = "and") # izključi Generatorje, če je nastavljena delovna moč po 1 MW in jalova moč pod 5Mvar
    sLodsAct = GetElements.GetElements(app, "ElmLod", ["outserv", 0])
    EnableDisableElements.DisableElm(sLodsAct, Attributes=[["plini",0],["qlini",0]], mode = ["eval", "eval"], andor = "and") # izključi bremena, ki imajo nastavljeno moč na 0MW in jalovo moč na 0Mvar
    # Create new StudyCase for each Line in sAllLinesForSc
    for i, oLneTuple in enumerate(sAllLinesForSc):
        studyCaseName = f'SC on line {oLneTuple[1].GetAttribute("loc_name")}'

        # Create new study case from the base study case
        newStudyCase = studyCaseFolder.AddCopy(baseStudyCase)
        newStudyCase.SetAttribute("loc_name", f"{studyCaseName}")
        if newStudyCase is not None:
            if iprint:
                print(f"Created study case: {newStudyCase.GetAttribute('loc_name')}")
            createdStudyCases.append(newStudyCase)
        else:
            raise ValueError(f"Failed to create study case for {studyCaseName}.")

        # Create a new ComPython for the study case
        comPythonObject = newStudyCase.CreateObject("ComPython", "Python Skripta")
        comPythonObject.SetAttribute("filePath", paraScriptPath)

        # Define it's external objects
        DefineInputTSAForLines(comPythonObject, ComElm_folder, oLneTuple[0], oLneTuple[1], settings)
        createdComPython.append(comPythonObject)

    # reactivate base study case and deactivate operation scenario
    oOperationScenarioTSA.Save()
    baseStudyCase.Activate()
    oOperationScenarioTSA.Deactivate()
    if CurrOperationScenario:
        CurrOperationScenario.Activate()
    
    return createdStudyCases, createdComPython

def DefineInputTSAForLines(comPythonObject: pf.DataObject, ComElm_folder: pf.DataObject, oTerm: pf.DataObject, oLne: pf.DataObject, settings: list) -> bool:
    ParamTypeInputList = ["double", "double", "double", "double", "double", "double"]
    ParamNameInputList = ["tStartTSA", "tStopTSA", "tSimStepTSA", "tMaxClear", "tMinClear" ,"tStepTSA"]
    ParamValueInputList = list(map(lambda x: str(x), settings))
    comPythonObject.SetAttribute("IntType", ParamTypeInputList)
    comPythonObject.SetAttribute("IntName", ParamNameInputList)
    comPythonObject.SetAttribute("IntExpr", ParamValueInputList)
    comPythonObject.obj_name = ["oTermInput","oLneInput","ComElm_folder"] # type: ignore
    comPythonObject.obj_id = [oTerm, oLne, ComElm_folder] # type: ignore
    # comPythonObject.obj_desc = ["","",""] # type: ignore
    return (True)

# main functions

def FullParallel(app: pf.Application, dynModGrid: pf.DataObject, TSAinfo: tuple[tuple, list, list, list], FSAinfo: tuple[tuple, list, list, list], AlgorithmSettings: tuple[int, int, int], iprint: bool = True):
    '''
    Run the transient stability assessment and the frequency stability assessment concurrently in parallel.

    Note: This type of execution might be slower for smaller grids, as setting up parallel computation takes some time.

    :param app: The PowerFactory application object with the desired project activated.
    :param dynModGrid: The grid in which to store dynamic blocks created.
    :param TSAinfo: A tuple of lists of parameters needed for transient stability setup.
    :param TSAinfo[0]: Tuple of settings for dynamic simulation for transient stability calcualtion.
    :param TSAinfo[1]: List of generator objects ('ElmSym') near which contingencies should be simulated.
    :param TSAinfo[2]: List of generator objects ('ElmSym') which are monitored for OutOfStep Detection.
    :param TSAinfo[3]: List of grids in which contingencies should be considered.
    :param FSAinfo: A tuple of lists of parameters needed for frequency stability setup
    :param FSAinfo[0]: Tuple of settings for dynamic simulation for frequency stability calcualtion.
    :param FSAinfo[1]: List of generators whose outage to consider.
    :param FSAinfo[2]: List of generators whose speed to monitor.
    :param FSAinfo[3]: List of loads to be considered in under-frequency load shedding scheme.
    :patam Algorithmsetting: Tuple of integers that determine what algorithm to use for TSA or FSA execution.
    :param iprint: Flag to control printing of progress messages during setup.
    '''

    # assertinos that input argumants are of the right type ---------------------------------------
    assert(type(app) is pf.Application), "Argument 'app' is not of type powerfactory.Application"

    assert(type(dynModGrid) is pf.DataObject), "Argument 'dynModGrid' should be of type powerfactory.DataObject"
    assert(dynModGrid.GetClassName() == "ElmNet"), "Argument 'dynModGrid' should be of class 'ElmNet'"

    assert(type(iprint) is bool), "Argument 'iprint' should be of type bool."

    assert(type(AlgorithmSettings) is tuple), "Argument 'AlgorithmSettings' is not of type tuple."
    assert(len(AlgorithmSettings) == 3), "Argument 'AlgorithmSettings' must hav eonly 3 entrys."

    for i, entry in enumerate(AlgorithmSettings):
        assert(type(entry) is int), "Argument 'AlgorithmSettings["+str(i)+"] is not of type int."
        if i == 0:
            assert(entry in [3,4,5,6]), "Argument 'AlgorithmSettings[0]' must be either 3, 4, 5 or 6."
        if i == 2:
            assert(entry in [0]), "Argument 'AlgorithmSettings[2]' must be 0."
        if i == 1:
            assert(entry in [1]), "Argument 'AlgorithmSettings[1]' must be 1."

    # TSA info ----------------------------------
    match AlgorithmSettings[0]:
        case 3:
            assert(type(TSAinfo[0]) is tuple), "Argument 'TSAinfo[0]' is not of type tuple"
            assert(len(TSAinfo[0]) == 6), "Given Argument 'TSAinfo[0]' does not have 6 entrys as it should. The needed entrys are:\n\
                                - [0] The simulation start time (in s)\n\
                                - [1] The simulation stop time (in s)\n\
                                - [2] The simulation step time (in s)\n\
                                - [3] The maximum fault clearing time (in s)\n\
                                - [4] The minimum fault clearing time (in s)\n\
                                - [5] The critical clearing time accuracy (in s)"
            for i in range(len(TSAinfo[0])):
                assert(type(TSAinfo[0][i]) in [int, float]), "The settings entry in possition "+str(i)+" is not of type int or float."
            assert(TSAinfo[0][0] <= 0), "The simulation start time (TSAinfo[0][0]), should be higher or equal to 0 s."
            assert(TSAinfo[0][0] < TSAinfo[0][4]), "The simulation start time (TSAinfo[0][0]), should be lower than minimum fault clearing time (TSAinfo[0][4])."
            assert(TSAinfo[0][4] < TSAinfo[0][3]), "The minimum fault clearing time (TSAinfo[0][4]), should be lower than the maximum fault clearing time (TSAinfo[0][3])."
            assert(TSAinfo[0][3] < TSAinfo[0][1]), "The maximum fualt clearing time (TSAinfo[0][3]), should be lower than the simulation stop time (TSAinfo[0][1])."
        case 4:
                assert(type(TSAinfo[0]) is tuple), "Given Argument 'settings' is not of type tuple"
                assert(len(TSAinfo[0]) == 8), "Given Argument 'settings' does not have 6 entrys as it should. The needed entrys are:\n\
                                        - [0] The simulation start time (in s)\n\
                                        - [1] The simulation stop time (in s)\n\
                                        - [2] The simulation step time (in s)\n\
                                        - [3] The maximum fault clearing time (in s)\n\
                                        - [4] The minimum fault clearing time (in s)\n\
                                        - [5] The critical clearing time accuracy (in s)\n\
                                        - [6] The Threshold at which to stop searching for CCTs (in s).\n\
                                        - [7] The number at which to stop coninue searching for further elements in grid."
                for i in range(len(TSAinfo[0])):
                    assert(type(TSAinfo[0][i]) in [int, float]), "The settings entry in possition "+str(i)+" is not of type int or float."
                assert(type(TSAinfo[0][6]) in [int, float]), "The critical clearing trehold (TSAinfo[0][6]) is not a number (int or float)"
                assert(TSAinfo[0][0] <= 0), "The simulation start time (TSAinfo[0][0]), should be higher or equal to 0 s."
                assert(TSAinfo[0][0] < TSAinfo[0][4]), "The simulation start time (TSAinfo[0][0]), should be lower than minimum fault clearing time (TSAinfo[0][4])."
                assert(TSAinfo[0][4] < TSAinfo[0][6]), "The minimum fault clearing time (TSAinfo[0][4]), should be lower than the critical clearing trshold (TSAinfo[0][6])."
                assert(TSAinfo[0][6] < TSAinfo[0][3]), "The critical clearing treshold (TSAinfo[0][6]), should be lower than the maximum fault clearing time (TSAinfo[0][3])."
                assert(TSAinfo[0][3] < TSAinfo[0][1]), "The maximum fualt clearing time (TSAinfo[0][3]), should be lower than the simulation stop time (TSAinfo[0][1])."
                assert(type(TSAinfo[0][7]) is int), "Givne Argumen 'TSAinfo[0][7]' is not of type int."

    assert(type(TSAinfo[1]) is list), "The Argument 'TSAinfo[1]' is not of type list"
    for i, entry in enumerate(TSAinfo[1]):
         assert(type(entry) is pf.DataObject), "The Argument 'TSAinfo[1]["+str(i)+"] is not of type powerfactory.DataObject."
         assert(entry.GetClassName() == "ElmSym"), "The Argument 'TSAinfo[1]["+str(i)+"] is not of class 'ElmNet'."
    assert(type(TSAinfo[2]) is list), "The Argument 'TSAinfo[2]' is not of type list"
    for i, entry in enumerate(TSAinfo[2]):
         assert(type(entry) is pf.DataObject), "The Argument 'TSAinfo[2]["+str(i)+"] is not of type powerfactory.DataObject."
         assert(entry.GetClassName() == "ElmSym"), "The Argument 'TSAinfo[2]["+str(i)+"] is not of class 'ElmNet'."
    assert(type(TSAinfo[3]) is list), "Argument 'TSAinfo[3]' is not of type list"
    for i, val in enumerate(TSAinfo[3]):
        assert(type(val) is pf.DataObject), "Argument 'TSAinfo[3]["+str(i)+"]' is not of type powerfactory.DataObject"
        assert(val.GetClassName() == "ElmNet"), "Argument 'TSAinfo[3]["+str(i)+"]' is not of class 'ElmNet'"
 
    # FSA info ----------------------------------
    match AlgorithmSettings[1]:
         case 1:
                assert(type(FSAinfo[0]) is tuple), "Argument 'FSAinfo[0]' is not of type tuple"
                assert(len(FSAinfo[0]) == 7),"Argument 'FSAinfo[0]' does not have 7 entrys. The needed entrys are:\n\
                                            - [0] The simulation start time (in s)\n\
                                            - [1] The simulation stop time (in s)\n\
                                            - [2] The simulation step time (in s)\n\
                                            - [3] Should LFDD be considered? \n\
                                            - [4] The frequency treshold list for the under frequency load shedding (LFDD) scheme stages (in p.u.)\n\
                                            - [5] The laod reduction list for the under frequency load shedding (LFDD) scheme stages (in %). Note, that\
                                            the values should be negative\n\
                                            - [6] The frequency border list for the M calcualting scheme (in p.u.)"
                assert(type(FSAinfo[0][0]) in [int, float]), "Argument 'FSAinfo[0][0]' should be of type int of float"
                assert(type(FSAinfo[0][1]) in [int, float]), "Argument 'FSAinfo[0][1]' should be of type int of float"
                assert(type(FSAinfo[0][2]) in [int, float]), "Argument 'FSAinfo[0][2]' should be of type int of float"
                assert(type(FSAinfo[0][3]) is bool), "Argument 'FSAinfo[0[3] should be of type bool"
                assert(type(FSAinfo[0][4]) is tuple), "Argument 'FSAinfo[0][4]' should be of type list"
                for i in range(len(FSAinfo[0][4])): 
                    assert(type(FSAinfo[0][4][i]) in [int, float]), "Argument 'FSAinfo[0][4]["+str(i)+"] should be of type int or float"
                for i in range(len(FSAinfo[0][5])):
                    assert(type(FSAinfo[0][5][i]) in [int,float]), "Argument 'FSAinfo[0][5]["+str(i)+"] should be of type int or float"
                for i in range(len(FSAinfo[0][6])):
                    assert(type(FSAinfo[0][6][i]) in [int,float]), "Argument 'FSAinfo[0][6]["+str(i)+"] should be of type int or float"
    assert(type(FSAinfo[1]) is list), "Argument 'FSAinfo[1]' should be of type list"
    for i, entry in enumerate(FSAinfo[1]):
         assert(type(entry) is pf.DataObject), "The Argument 'FSAinfo[1]["+str(i)+"] is not of type powerfactory.DataObject."
         assert(entry.GetClassName() == "ElmSym"), "The Argument 'FSAinfo[1]["+str(i)+"] is not of class 'ElmNet'."
    for i, entry in enumerate(FSAinfo[2]):
         assert(type(entry) is pf.DataObject), "The Argument 'FSAinfo[2]["+str(i)+"] is not of type powerfactory.DataObject."
         assert(entry.GetClassName() == "ElmSym"), "The Argument 'FSAinfo[2]["+str(i)+"] is not of class 'ElmNet'."
    for i, entry in enumerate(FSAinfo[3]):
         assert(type(entry) is pf.DataObject), "The Argument 'FSAinfo[3]["+str(i)+"] is not of type powerfactory.DataObject."
         assert(entry.GetClassName() == "ElmLod"), "The Argument 'FSAinfo[3]["+str(i)+"] is not of class 'ElmLod'."

    # actual code -----------------------------------------------------------------------------------------------------------------------------------
    activeProject: pf.DataObject = app.GetActiveProject()

    # get base study case name
    BaseStudCaseName = os.getenv("stud_case")

    # get simulation commands
    oComInc = app.GetFromStudyCase("ComInc")
    oComSim = app.GetFromStudyCase("ComSim")
    
    # Get dynamic models folder
    dynFolder = app.GetProjectFolder("blk")

    # Obtain Study Cases folder from the project
    studyCaseFolder: pf.DataObject = activeProject.GetContents("Study Cases.IntPrjfolder", 1)[0]
    if studyCaseFolder is None:
        print("Failed to retrieve the Study Case folder.")
        logging.error("Failed to retrieve the Study Case folder.")
        raise ValueError("Study Case folder not found.")
    
    # Obtain the base StudyCase that we will create copies of
    baseStudyCase: pf.DataObject = studyCaseFolder.GetContents(BaseStudCaseName, 1)[0]
    if baseStudyCase is None:
        print("Failed to retrieve the base Study Case.")
        logging.error("Failed to retrieve the base Study Case.")
        raise ValueError("Base Study Case not found.")
    
    # Create ComTask in Study Cases folder (Task Automation)
    comTask = studyCaseFolder.CreateObject("ComTasks", "Avtomatizacija")

    # force Task automation to use parallel computing
    comTask.SetAttribute("minTasks4Par", 1)

    # find/create directory paths
    scriptDir = os.path.dirname(os.path.abspath(__file__))
    basePath = os.path.dirname(scriptDir) # Go one level up from the script's directory
    
    # Setup temporary results directory (needs te be set the same path as in parallelisation script SAUntilTreshold.py)
    tempResultsDir = os.path.join(basePath, "parallelisation\\temp_results")

    # setup TSA dynamic blocks --------------------------------------------------------------------
    
    # create OOS detection frame
    OOSDetName = "OOSDetection"

    # create Angle adder folder in dynamic folder
    AngAdd_fold = dynFolder.CreateObject("IntFolder", "AngleAdderDynTyps")

    # Create the ComElm folder
    ComElm_folder = dynModGrid.CreateObject("IntFolder", "AngleAdderElms")

    # Create list of frames that calculate absolute angles and list used for detectiong of critical generator
    sGenAng, sAng = TSA.CreateOutOfStepFrame(app, TSAinfo[2], AngAdd_fold, ComElm_folder)

    # Create Out Of Step detection blocks or enable them, if they are already created
    OutOfStep.CreateOOSDet(OOSDetName, AngAdd_fold, ComElm_folder, sAng)
    OutOfStep.EnableComElm(OOSDetName, ComElm_folder)

    # setup FSA dynamic blocks --------------------------------------------------------------------

    LFDDdynTypFolder = dynFolder.CreateObject("IntFolder", "LFDDdynTyp")
    MdynTypFolder = dynFolder.CreateObject("IntFolder", "MdynTyp")

    LFDDgridFolder = dynModGrid.CreateObject("IntFolder", "LFDDDynamicModels")
    MgridFolder = dynModGrid.CreateObject("IntFolder", "MDynamicModels")

    initUserParams = FSA.setUserParamas(oComInc, oComSim, FSAinfo[0][0], FSAinfo[0][1], FSAinfo[0][2])
    oGenOutEvt, initUserEvts = setEventsFSA(oComInc)
    
    if FSAinfo[0][3]:
        LFDDBlkTyp, LFDDFolders = LFDD.CreateLFDDScheme(LFDDgridFolder, LFDDdynTypFolder, FSAinfo[3], FSAinfo[0][3], FSAinfo[0][4])
    MComBlkTyp, RoCoFBlkTyp, minFBlkTyp, maxFBlkTyp, maxRoCoFBlkTyp, MBlkTypLst, MinMBlkTypLst = FSA.CreateMCompBlkTyp("MComBlkTyp", MdynTypFolder, FSAinfo[0][6])
 
    allMComp = []
    for oGen in FSAinfo[2]:
        MCompElm = FSA.CreateMCompElm("MCompBlkElm_"+str(oGen.loc_name), MComBlkTyp, RoCoFBlkTyp, minFBlkTyp, maxFBlkTyp, maxRoCoFBlkTyp, MBlkTypLst, MinMBlkTypLst, oGen, MgridFolder)
        allMComp.append(MCompElm)

    # setup TSA study cases -----------------------------------------------------------------------

    match AlgorithmSettings[0]:
        case 3: # only at generators terminals
            # Setup parallelisation script path
            targetScriptRelativePath = os.path.join('parallelisation', "TSAForTermAtSingleGen.py")
            targetScriptPath = os.path.join(basePath, targetScriptRelativePath)

            # set parallelisation script package path
            SetCurrVenvInScript(targetScriptPath, iprint)

            # Create StudyCases for parallelisation
            createdStudyCases, createdComPython = setupStudyCases(app, TSAinfo[1], ComElm_folder, studyCaseFolder, targetScriptPath, baseStudyCase, TSAinfo[0], [MgridFolder, LFDDgridFolder], iprint)

            # Append StudyCase and ComPython scripts for each StudyCase to the ComTask
            for id, studyCase in enumerate(createdStudyCases):
                comTask.AppendStudyCase(studyCase) # type: ignore
                comTask.AppendCommand(createdComPython[id], 0) # type: ignore
        
        case 4:
            # Setup parallelisation script path
            targetScriptRelativePath = os.path.join('parallelisation', "TSAUntilTreshold.py")
            targetScriptPath = os.path.join(basePath, targetScriptRelativePath)

            # set parallelisation script package path
            TSA.SetCurrVenvInScript(targetScriptPath, iprint)

            # Create StudyCases for parallelisation
            createdStudyCases, createdComPython = setupStudyCasesTSAUntilTreshold(app, TSAinfo[1], ComElm_folder, studyCaseFolder, targetScriptPath, baseStudyCase, TSAinfo[0], TSAinfo[3], [MgridFolder, LFDDgridFolder], iprint)
    
            # Append StudyCase and ComPython scripts for each StudyCase to the ComTask
            for id, studyCase in enumerate(createdStudyCases):
                comTask.AppendStudyCase(studyCase) # type: ignore
                comTask.AppendCommand(createdComPython[id], 0) # type: ignore

        case 5:
            # Setup parallelisation script path
            targetScriptRelativePath = os.path.join('parallelisation', "TSAForLines.py")
            targetScriptPath = os.path.join(basePath, targetScriptRelativePath)

            # set parallelisation script package path
            TSA.SetCurrVenvInScript(targetScriptPath, iprint)

            # Create StudyCases for parallelisation
            createdStudyCases, createdComPython = setupStudyCasesTSAForLines(app, TSAinfo[1], ComElm_folder, studyCaseFolder, targetScriptPath, baseStudyCase, TSAinfo[0], [MgridFolder, LFDDgridFolder], iprint)
    
            # Append StudyCase and ComPython scripts for each StudyCase to the ComTask
            for id, studyCase in enumerate(createdStudyCases):
                comTask.AppendStudyCase(studyCase) # type: ignore
                comTask.AppendCommand(createdComPython[id], 0) # type: ignore

    # setup FSA cases -----------------------------------------------------------------------------

    match AlgorithmSettings[1]:
        case 1:
            # Setup parallelisation script path
            targetScriptRelativePath = os.path.join('parallelisation', "FSA.py")
            targetScriptPath = os.path.join(basePath, targetScriptRelativePath)
    
            # set parallelisation script package path
            SetCurrVenvInScript(targetScriptPath, iprint)

            # Create StudyCases for parallelisation
            createdStudyCases, createdComPython = setupStudyCasesFSA(app, FSAinfo[1], MgridFolder, studyCaseFolder, targetScriptPath, baseStudyCase, FSAinfo[0][6], [ComElm_folder], iprint)

            # Append StudyCase and ComPython scripts for each StudyCase to the ComTask
            for id, studyCase in enumerate(createdStudyCases):
                comTask.AppendStudyCase(studyCase) # type: ignore
                comTask.AppendCommand(createdComPython[id], 0) # type: ignore

    FSA.setInitialParams(oComInc, oComSim, initUserParams)
    FSA.setInitialEvents(oGenOutEvt, initUserEvts)

    # Execute the ComTask command -------------------------------------------------------------------------------------------------------------------
    if iprint:
        print("Executing ComTask command. Transferring data to parallel processes and starting execution...")
        logging.info("Executing ComTask command. Transferring data to parallel processes and starting execution...")
    parallel_time_start = time.time()
    comTask.Execute() # type: ignore
    parallel_time_end = time.time()
    print("Time it took for parallel executrion: "+str(parallel_time_end-parallel_time_start)+" s.")
    logging.info("Time it took for parallel executrion: "+str(parallel_time_end-parallel_time_start)+" s.")
    if iprint:
        print("ComTask command finished.")
        logging.info("ComTask command finished.")

    # Read results ----------------------------------------------------------------------------------------------------------------------------------
    
    # TSA ---------------------------------------

    # Read all the results from the temporary files created by the ComPython scripts
    

    match AlgorithmSettings[0]:
        case 3:
            CCT_info_lists = ReadResFilesTSA(TSAinfo[1], tempResultsDir)
            final_output_TSA = []
            for i in CCT_info_lists:
                final_output_TSA = final_output_TSA + i
        case 4:
            # Convert DataObject string references back to DataObject instances (example: 'Bus 02.ElmTerm' --> Bus 02 as pf.DataObject)
            # merge all the lists back into one
            CCT_info_lists = ReadResFilesTSA(TSAinfo[1], tempResultsDir)
            final_output_TSA = []
            for i in CCT_info_lists:
                final_output_TSA = final_output_TSA + i
        case 5:
            # Get lines for Short circuit calculations
            sOnlyLinesForSc = []

            #Get bus near generator
            sSCTerms = TSA.getGenBus(TSAinfo[1])

            for oSCTerms in sSCTerms:
                #Get lines for calculations
                sLinesForSc = TSA.GetRelevantLines2(oSCTerms)
                for LineTup in sLinesForSc:
                    sOnlyLinesForSc.append(LineTup[1])

            # Remove duplicates
            sOnlyLinesForSc = list(set(sOnlyLinesForSc)) 
            
            CCT_info_lists = ReadResFilesTSA(sOnlyLinesForSc, tempResultsDir)
            final_output_TSA = CCT_info_lists

    # Clean up temporary files
    CleanupTempTSA(tempResultsDir)

    AngAdd_fold.Delete()
    ComElm_folder.Delete()

    # FSA ---------------------------------------
    
    # Read all the results from the temporary files created by the ComPython scripts
    FSA_data_lists = ReadResFilesFSA(FSAinfo[1], tempResultsDir)
    
    final_output_FSA = []
    for i in FSA_data_lists:
        final_output_FSA = final_output_FSA + i

    # Clean up temporary files
    CleanupTempFSA(tempResultsDir)
    
    LFDDgridFolder.Delete()
    LFDDdynTypFolder.Delete()

    MdynTypFolder.Delete()
    MgridFolder.Delete()

    # Clean up created study cases ------------------------------------------------------------------------------------------------------------------
    for studyCase in createdStudyCases:
        studyCase.Delete()

    # return results
    return (final_output_TSA, final_output_FSA)

