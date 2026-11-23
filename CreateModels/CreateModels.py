'''
Author: Matjaz Skrlec
date: 06. 10. 2024
version: 1.0
description: This module is used for importing and creating powerfactory projects.
'''

import os
import sys
from pathlib import Path
import logging
from dotenv import load_dotenv
from PFSupport.Utils import SetToInstantPruge
load_dotenv()
sys.path.append(os.getenv("PowerfactoryPyFilePath"))
import powerfactory as pf

def ImportPfd(app: pf.Application, PfdFileName: str, PfdPrjName: str, StudCaseName = None, PrjFolder = None) -> pf.DataObject:
    assert(type(app) == pf.Application), "Argument 'app' is not of type powerfactory.Application."
    assert(type(PfdFileName) == str), "Argument 'PfdFileName' is not of type string."
    assert(type(PfdPrjName) == str), "Argument 'PfdPrjName' is not  of tye string"
    assert(type(PrjFolder) in [pf.DataObject, type(None)]), "Argument 'PrjFolder' is not of powerfactory.DataObject or None type."

    currPrj = app.GetActiveProject()
    if currPrj:
        currPrj.Deactivate()

    # check if file exists
    if not Path(PfdFileName).exists():
        print(f"File {PfdFileName} was not found. Exiting process.")
        logging.warning(f"File {PfdFileName} was not found. Exiting process.")
        exit()

    ComImp = app.GetFromStudyCase("ComPfdImport")
    ComImp.SetAttribute("g_file", PfdFileName)
    if PrjFolder:
        ComImp.SetAttribute("g_target", PrjFolder)
        PrjFolderName = PrjFolder.GetAttribute("loc_name")
        PrjPath = PrjFolderName+"\\"+PfdPrjName
    else:
        PrjPath = PfdPrjName
    ComImp.Execute()
    app.ActivateProject(PrjPath)
    # activate relevant study case
    if StudCaseName:
        for oStud in app.GetProjectFolder("study").GetContents():
            if oStud.GetAttribute("loc_name") == StudCaseName:
                oStud.Activate()
                oStud.Consolidate()
    SetToInstantPruge(app)
    Prj = app.GetActiveProject()
    Prj.Deactivate()
    return(Prj)

def ImportDgsData(app: pf.Application, Prj: pf.DataObject, DgsFile: str) -> bool: # this can be used to import DGS data
    assert(type(app) == pf.Application), "Argument 'app' is not of type powerfactory.Application."
    assert(type(Prj) == pf.DataObject), "Argument 'Prj' is not of type powerfactory.DataObject."
    assert(type(DgsFile) == str), "Argument 'DgsFile' is not of type string."
    
    fixed_DGS_file_name = DgsFile

    # check if file exists
    if not Path(fixed_DGS_file_name).exists():
        print(f"File {fixed_DGS_file_name} was not found. Exiting process.")
        logging.warning(f"File {fixed_DGS_file_name} was not found. Exiting process.")

    ComImp = app.GetFromStudyCase("ComImport")
    ComImp.SetAttribute("iopt_prj", 1)
    ComImp.SetAttribute("pAddPrj", Prj)
    ComImp.SetAttribute("fFile", fixed_DGS_file_name)
    ComImp.Execute()
    Prj.Deactivate()
    return(True)