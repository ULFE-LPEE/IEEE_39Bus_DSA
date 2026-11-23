'''
Author: Matjaz Skrlec
date: 18. 02. 2024
version: 1.0
description: This is the utils folder for powerfactory, random functions for powerfactory are stored here
'''

## imports
import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.getenv("PowerfactoryPyFilePath"))
import powerfactory as pf
import logging
from typing import List

def EmpyUserFile(app: pf.Application, FileName: str):
    PrjFolder = None
    CurrUser = app.GetCurrentUser()
    sPrjFolder = CurrUser.GetContents("*.IntFolder")
    for oFolder in sPrjFolder:
        if oFolder.GetAttribute("loc_name") == FileName:
            PrjFolder = oFolder
    if PrjFolder:
        for oPrj in PrjFolder.GetContents():
            oPrj.Deactivate()
            oPrj.Delete()
        return (True)
    else:
        print("Could not find desired folder")
        return(False)

def clearOutputWindow(app: pf.Application):
    '''
    This function  tclearshe output window in powerfactory.
    '''
    outputWindow: pf.OutputWindow = app.GetOutputWindow()
    outputWindow.Clear()

def getOutputWindowContent(app: pf.Application) -> List[str]:
    '''
    This function returns the content of the output window in powerfactory as list of strings.
    Each string is a line in the output window.
    '''
    outputWindow: pf.OutputWindow = app.GetOutputWindow()
    outputContent: List[str] = outputWindow.GetContent()

    return outputContent

def excludeElement(sElmList: list, Attributes: list = []) -> list:
    sReturnList = []
    for oElm in sElmList:
        if oElm.GetAttribute(Attributes[0]) != Attributes[1]:
            sReturnList.append(oElm)
    return sReturnList

def SetToInstantPruge(app: pf.DataObject) -> list:
    oActPrj = app.GetActiveProject()
    if not oActPrj:
        print("Active Project was not found, could not set purging time to 0.")
        logging.warning("Active Project was not found, could not set purging time to 0.")
        return False
    oActPrj.SetAttribute("st_retention", 1)
    oActPrj.SetAttribute("st_purgeauto", 0)
    oActPrj.SetAttribute("st_purgeautoprd", 1)
    return True
