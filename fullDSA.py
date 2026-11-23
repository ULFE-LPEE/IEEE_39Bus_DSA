'''
Author: Matjaz Skrlec
date: 09. 01. 2024
version: 1.0
description: This is the main program that runs the full DSA procedure
'''
#--------------------------------------------------------------------------------------------------
## imports
import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.getenv("PowerfactoryPyFilePath"))
import powerfactory as pf
import DSA.RunDSA as RunDSA
import DSA.HandleFiles as HandleFiles
import CreateModels.CreateModels as CreateModels
import time
import logging
import PFSupport.GetElements as GetElements
import PFSupport.EnableDisableElements as EnableDisableElements
import random_setpoint


#--------------------------------------------------------------------------------------------------
## variable parameters of code

# chose which algorith to use for calculation
# posisiton 0 is for Transients Stability:  0 - sequential calculation only at generators terminals
#                                           1 - sequential calculation at generators terminals and connected lines
#                                           2 - sequential calculation at generators terminals and nearby elements until CCT is larger than predefined treshold
#                                           3 - parallel calculation only at generators terminals
#                                           4 - parallel calculation at generators terminals and nearby elements until CCT is larger than predefined treshold or a predefined number of elements haven't been considered
#                                           5 - parallel calculation at lines near generators that aren't connected to it radialy
#
# position 1 is for Frequency stability:    0 - sequential calculation of generator outages record 1 RoCoF value and M values
#                                           1 - parallel calculation of generator outages record 1 RoCoF value and M values
#                                           2 - parallel calculation of generators record RoCoF values only
# position 2 is for Small signal stability: 0 - calcualte for the current operation state
Algorithm_settings = (5,1,0)
# choose what kind of parallel computing you want to execute:
#                                           0 - calculate each stability setting seperately
#                                           1 - calculate TSA nad FSA at once
# WARNING: if you want to calculate TSA and FSA at once, Algorithm_setting[0] must be either 3,4,5 and Algorithm_setting[2] must be 1 (code for action 2 hasent been developed yet).
Parallel_algorithm_setting = 0

randomise_setpoint = True

# files for import
IEEE39_bus_Pfd_file = os.getenv("Pfd_file")

# model name, already imported into pf
prj_str = os.getenv("prj_str")
# SLO study case for dynamic simulations
stud_case = os.getenv("stud_case")

# Logger file
logFile = f"results\\LOG\\log.log"

# Grids
Grid_name = (os.getenv("grid_name"))

# Main file export type
MainDirSaveFlag = int(os.getenv("MainDirSaveFlag")) 
# 0 - append temporary file to an existing main file (or create mian file if it doens't exits).
# 1 - copy temporary file to main folder and rewrite its name.

# Powerfactory Worksapce
PF_Workspace_flag = os.getenv("PF_Workspace_flag")
# 0 - default powerfactory Workspace
# 1 - modified powerfactory Workspace
#--------------------------------------------------------------------------------------------------
#setup logger
logging.basicConfig(filename = logFile, filemode = "a", level = logging.INFO)
print("-------------------------------------------------------------------------------------------")
print("Calculating new DSA case")
print("Slo Pfd File:\n%s" % IEEE39_bus_Pfd_file)
logging.info("-------------------------------------------------------------------------------------------")
logging.info("Calculating new DSA case")
logging.info("Slo Pfd File:\n%s" % IEEE39_bus_Pfd_file)

t_program_start = time.time()

match PF_Workspace_flag:
    case "0":
        ### this is the normal way to run start powerfactory
        # start powerfactory in non-interactive mode
        print("-------------------------------------------------------------------------------------------")
        logging.info("-------------------------------------------------------------------------------------------")
        print("opening PF")
        logging.info("Opening PF")
        app = pf.GetApplicationExt()
        # disable user break button
        app.SetGuiUpdateEnabled(0)
        app.SetProgressBarUpdatesEnabled(0)

    case "1":
        # ####################################################################################################
        # start PowerFactory
        # ####################################################################################################
        # activate project
        # This way of starting powerfactory is good if you intend to run multiple analysis runs,
        # as it allows you to create a new workspace with your own initialisation parameters. If
        # you run powerfatory normaly you may run into the issue of the db.bn file in the usual
        # Workspace bloating, even if you delete the projects every run and empty the recycle bin.
        try:
            print('Before GetApplicationExt() start')
            iniPath=os.getenv("powerfactoryIniFile") 
            app = pf.GetApplicationExt(None,None,'/ini '+ iniPath+' /readonlymode')
            #app = pf.GetApplicationExt(None,None,'/ini '+ iniPath)
            print('After GetApplicationExt() start')
            currentUsername=app.GetCurrentUser().GetAttribute("e:loc_name")
            print('User: ' + currentUsername)
            currentWorkspaceDirectory=app.GetWorkspaceDirectory()
            print('Workspace: ' + currentWorkspaceDirectory)
        except pf.ExitError as resExport:
            print('Error opening Power Factory - error code: %s' % resExport.code)
            raise Exception("Unable to open Power Factory - application execution aborted!")
        except Exception:
            print('Unable to open Power Factory (second Exception in try/exception) - application execution aborted!',exc_info=True)
    case _:
        sys.exit("Variable 'PF_Workspace_flag' is set to a value not allowed. Only the strings '0' and '1' are allowed.")


# Get or create Project folder
CurrUser = app.GetCurrentUser()
sPrjFolder = CurrUser.GetContents("*.IntFolder")
folder_found_flag = False
for oFolder in sPrjFolder:
    if oFolder.GetAttribute("loc_name") == "full_execution":
        PrjFolder = oFolder
        folder_found_flag = True
if not folder_found_flag:
    PrjFolder = CurrUser.CreateObject("IntFolder", "full_execution")
oCombFolder = PrjFolder

print("-------------------------------------------------------------------------------------------")
logging.info("-------------------------------------------------------------------------------------------")
print("Importing project")
logging.info("Importing project")
oPrj = CreateModels.ImportPfd(app, IEEE39_bus_Pfd_file, prj_str, stud_case, PrjFolder)
oPrj.Activate()
print("Project Imported successfully.")
logging.info("Project Imported successfully.")

t_program_import = time.time()

##-----------------------------------------------------
## calculating stability indicies
# disable elements that should not be considered

# #Disable Generators whose absolute active power is below 1 MW and absolute reactive power is below 5 MVAr
# sGensAct = GetElements.GetElements(app, "ElmSym", ["outserv", 0])
# EnableDisableElements.DisableElm(sGensAct, Attributes = [["pgini", 1],["qgini", 5]], mode = ['absmax', 'absmax'], andor = "and")

# #Disable Loads whose active power is 0 MW and absolute reactive power 0 MVAr
# sLodsAct = GetElements.GetElements(app, "ElmLod", ["outserv", 0])
# EnableDisableElements.DisableElm(sLodsAct, Attributes=[["plini",0],["qlini",0]], mode = ["eval", "eval"], andor = "and")

##------------------------------------------------------
## Randomly vary the current operation point
# set elements out of service:
if randomise_setpoint:
    print("-------------------------------------------------------------------------------------------")
    logging.info("-------------------------------------------------------------------------------------------")
    print("Randomising operating state.")
    logging.info("Randomising operating state.")
    random_setpoint.set_random_setpoint_operation_state(app, True, True, False, 0)
    print("Operating state successfully randomised.")
    logging.info("Operating state successfully randomised.")

# Get the grids in which to evaluate the wanted elements. This is useful if your model consists of multiple
# regions, but you want to analyse only one reagion of interest.
sGrids = app.GetCalcRelevantObjects("*.ElmNet")
contingencyGrids = []
for oGrid in sGrids:
    if Grid_name == oGrid.GetAttribute("loc_name") :
        dynamicModelGrid = oGrid # Grids in which the dynamic models used for evaluation are stored
        contingencyGrids.append(oGrid) # Grids in which contingencies are considered
        HGrids = [oGrid] # Grids in which inertia is evaluated

# get the elements you want to analyse
sGenAct = GetElements.GetElements(app, "ElmSym", [["outserv", 0],["cpGrid",dynamicModelGrid]]) # all generators
sTSAGenCCT = GetElements.GetElements(app, "ElmSym", [["outserv", 0],["cpGrid",dynamicModelGrid]]) # generators considered in CCT evaluation
sTSAGenMon = GetElements.GetElements(app, "ElmSym", [["outserv", 0],["cpGrid",dynamicModelGrid]]) # generators considered for monitoring of outage
sFSAGenOut = GetElements.GetElements(app, "ElmSym", [["outserv", 0],["cpGrid",dynamicModelGrid]]) # generators considered for outage faults
sFSAGenMon = GetElements.GetElements(app, "ElmSym", [["outserv", 0],["cpGrid",dynamicModelGrid]]) # generators considered for monitoring frequency
sFSALodLFDD = GetElements.GetElements(app, "ElmLod", [["outserv", 0],["cpGrid",dynamicModelGrid]]) # generators considered for low frequency demand disconnection
sSSSAGenMon = GetElements.GetElements(app, "ElmSym", [["outserv", 0],["cpGrid",dynamicModelGrid]]) # # generators considered for monitoring small signal stability

t_setup = time.time()

t_RunDSA, TSA_settings, FSA_settings, SSSA_settings = RunDSA.RunDSA(app, dynamicModelGrid, contingencyGrids, sTSAGenCCT, sTSAGenMon, sSSSAGenMon, sFSAGenOut, sFSAGenMon, sFSALodLFDD, HGrids, Algorithm_settings, Parallel_algorithm_setting, MainDirSaveFlag)

# delete the project as it is not needed anymore
oPrj.Delete()
## report how long each program step took

total_time = [t_program_start, t_program_import, t_setup] + t_RunDSA
## report how long each program step took (one TSA module)
match Parallel_algorithm_setting:
    case 0:
        print("-------------------------------------------------------------------------------------------")
        print("time for importing: %f s" % (total_time[1]-total_time[0]))
        print("time for seting up lists for DSA:  %f s" % (total_time[2]-total_time[1]))
        print("time for initialising DSA:%f s" % (total_time[3]-total_time[2]))
        print("time for loadflow calculations:  %f s" % (total_time[4]-total_time[3]))
        print("time for free run stability check: %f s" % (total_time[5]-total_time[4]))
        print("time for TSA calculation: %f s" % (total_time[6]-total_time[5]))
        print("time for FSA calculation: %f s" % (total_time[7]-total_time[6]))
        print("time for SSSA calculation: %f s" % (total_time[8]-total_time[7]))
        print("time for exporting: %f s" % (total_time[9]-total_time[8]))
        logging.info("-------------------------------------------------------------------------------------------")
        logging.info("time for importing: %f s" % (total_time[1]-total_time[0]))
        logging.info("time for seting up lists for DSA:  %f s" % (total_time[2]-total_time[1]))
        logging.info("time for initialising DSA:%f s" % (total_time[3]-total_time[2]))
        logging.info("time for loadflow calculations:  %f s" % (total_time[4]-total_time[3]))
        logging.info("time for free run stability check: %f s" % (total_time[5]-total_time[4]))
        logging.info("time for TSA calculation: %f s" % (total_time[6]-total_time[5]))
        logging.info("time for FSA calculation: %f s" % (total_time[7]-total_time[6]))
        logging.info("time for SSSA calculation: %f s" % (total_time[8]-total_time[7]))
        logging.info("time for exporting: %f s" % (total_time[9]-total_time[8]))
    case 1:
        print("-------------------------------------------------------------------------------------------")
        print("time for importing: %f s" % (total_time[1]-total_time[0]))
        print("time for seting up lists for DSA: %f s" % (total_time[2]-total_time[1]))
        print("time for initialising DSA: %f s" % (total_time[3]-total_time[2]))
        print("time for loadflow calculations: %f s" % (total_time[4]-total_time[3]))
        print("time for free run stability check: %f s" % (total_time[5]-total_time[4]))
        print("time for TSA and FSA calculation: %f s" % (total_time[6]-total_time[5]))
        print("time for SSSA calculation: %f s" % (total_time[7]-total_time[6]))
        print("time for exporting: %f s" % (total_time[8]-total_time[7]))
        logging.info("-------------------------------------------------------------------------------------------")
        logging.info("time for importing: %f s" % (total_time[1]-total_time[0]))
        logging.info("time for seting up lists for DSA: %f s" % (total_time[2]-total_time[1]))
        logging.info("time for initialising DSA: %f s" % (total_time[3]-total_time[2]))
        logging.info("time for loadflow calculations: %f s" % (total_time[4]-total_time[3]))
        logging.info("time for free run stability check: %f s" % (total_time[5]-total_time[4]))
        logging.info("time for TSA and FSA calculation: %f s" % (total_time[6]-total_time[5]))
        logging.info("time for SSSA calculation: %f s" % (total_time[7]-total_time[6]))
        logging.info("time for exporting: %f s" % (total_time[8]-total_time[7]))

# save info to csv
MethodUsed = (Algorithm_settings,(Parallel_algorithm_setting))

Temp_Info = os.getenv("Temp_Info")
Main_dir_Info = os.getenv("Main_dir_Info")
Main_Info = os.getenv("Main_Info")

HandleFiles.CreateTempCsvInfo(Temp_Info, MethodUsed, total_time, TSA_settings, FSA_settings, SSSA_settings)
match MainDirSaveFlag:
    case 0:
        HandleFiles.AppendTempCsvToMainCsv(Temp_Info,Main_Info)
    case 1:
        info_file_name = f"INFO.csv"
        HandleFiles.MoveTempCsvToMainDir(Temp_Info, Main_dir_Info, info_file_name)

