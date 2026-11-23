'''
Author: Matjaz Skrlec
date: 18. 02. 2024
version: 1.0
description: This program deletes the current "full_execution_test" file
'''
#--------------------------------------------------------------------------------------------------
## imports
import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.getenv("PowerfactoryPyFilePath"))
import powerfactory as pf
import PFSupport.Utils as PFUtils

# Powerfactory Worksapce
PF_Workspace_flag = os.getenv("PF_Workspace_flag")
# 0 - default powerfactory Workspace
# 1 - modified powerfactory Workspace

match PF_Workspace_flag:
    case "0":
        ### this is the normal way to run start powerfactory
        # start powerfactory in non-interactive mode
        print("-------------------------------------------------------------------------------------------")
        print("opening PF")
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
print("emptying folder")
PFUtils.EmpyUserFile(app, "full_execution")
app.ClearRecycleBin()