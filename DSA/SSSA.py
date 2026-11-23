'''
Author: Matjaz Skrlec
date: 04. 10. 2024
version: 1.0
description: This module is used for  small signal stability assessment using powerfactrory.
'''

#--------------------------------------------------------------------------------------------------
## imports
import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.getenv("PowerfactoryPyFilePath"))
import powerfactory as pf

def setUserParams(oComMod, oComRes, saveLeftEV: int, saveRightEV: int, saveParticFact: int, minReal: float, maxReal: float, minDampFreq: float, maxDampFreq: float, maxDampRat: float, file_EV: str):
    '''
    The funciton is for setting parameters of comands for the small signal stability assessment.
    '''

    assert(type(oComMod) == pf.DataObject), "Argument 'oComMod' is not of type powerfactory.DataObject"
    assert(oComMod.GetClassName() == "ComMod"), "Argument 'oComMod' is not a modal analysis command"
    assert(type(oComRes) == pf.DataObject), "Argument 'oComRes' is not of type powerfactory.DataObject"
    assert(oComRes.GetClassName() == "ComRes"), "Argument 'oComRes' is not results file"

    assert(saveLeftEV in [0,1]), "Argument 'saveLeftEV' is not 0 or 1."
    assert(saveRightEV in [0,1]), "Argument 'saveRightEV' is not 0 or 1."
    assert(saveParticFact in [0,1]), "Argument 'saveParticFact' is not 0 or 1."
    assert(type(minReal) in [int, float]), "Argument 'minReal' is not of type int or float"
    assert(type(maxReal) in [int, float]), "Argument 'maxReal' is not of type int or float"
    assert(type(minDampFreq) in [int, float]), "Argument 'minDampFreq' is not of type int or float"
    assert(type(maxDampFreq) in [int, float]), "Argument 'maxDampFreq' is not of type int or float"
    assert(type(maxDampRat) in [int, float]), "Argument 'maxDampRat' is not of type int or float"

    assert(type(file_EV) == str), "Argument 'file_EV' is not of type str"

    userSettings = []

    # modal analysis settings
    userSettings.append(oComMod.iLeft) 
    userSettings.append(oComMod.iRight) 
    userSettings.append(oComMod.iPart)

    userSettings.append(oComMod.isRecOscModesOnly)
    userSettings.append(oComMod.isRecMinReal) 
    userSettings.append(oComMod.isRecMinImag) 
    userSettings.append(oComMod.isRecMaxReal) 
    userSettings.append(oComMod.isRecMaxImag) 
    userSettings.append(oComMod.isRecMaxDampRat) 

    userSettings.append(oComMod.minReal) 
    userSettings.append(oComMod.minDampedFreq) 
    userSettings.append(oComMod.maxReal) 
    userSettings.append(oComMod.maxDampedFreq)
    userSettings.append(oComMod.maxDampRat)


    # set the recording of eigen vectors to 1 (active)
    oComMod.iLeft = saveLeftEV       #Controllability
    oComMod.iRight = saveRightEV     #Observability
    oComMod.iPart = saveParticFact   #Participation factors

    # mark the boxes for boundry conditions
    oComMod.isRecOscModesOnly = 1
    oComMod.isRecMinReal = 1
    oComMod.isRecMinImag = 1
    oComMod.isRecMaxReal = 1
    oComMod.isRecMaxImag = 1
    oComMod.isRecMaxDampRat = 1

    # set boundry conditions
    oComMod.minReal = minReal
    oComMod.minDampedFreq = minDampFreq
    oComMod.maxReal = maxReal
    oComMod.maxDampedFreq = maxDampFreq
    oComMod.maxDampRat = maxDampRat

    oComMod.outputType = 1

    oResFileMod = oComMod.GetAttribute("ResultFile")
    # export settings
    if (oComRes.pResult == None):
        oComRes.pResult = oResFileMod
        userSettings.append(oComRes.pResult)
    else:
        userSettings.append(oComRes.pResult)
        oComRes.pResult = oResFileMod
    userSettings.append(oComRes.iopt_exp)
    userSettings.append(oComRes.f_name)
    
    oResFileMod = oComMod.GetAttribute("ResultFile")
    #set params for exp file
    oComRes.iopt_exp = 6
    oComRes.f_name = file_EV

    userSettings.append(oComMod.outputType)

    return(userSettings)

def setInitialParams(oComMod, oComRes, settings: list):
    '''
    The funciton is for setting the initial user parameters.
    '''

    assert(type(oComMod) == pf.DataObject), "Argument 'oComMod' is not of type powerfactory.DataObject"
    assert(oComMod.GetClassName() == "ComMod"), "Argument 'oComMod' is not a modal analysis command"
    assert(type(oComRes) == pf.DataObject), "Argument 'oComRes' is not of type powerfactory.DataObject"
    assert(oComRes.GetClassName() == "ComRes"), "Argument 'oComRes' is not results file"

    assert(type(settings) == list), "Argument 'settings' should be list"
    assert(len(settings) == 18), "Argument 'settings' should countain 18 entrys"

    assert(type(settings[0]) == int), "Argument 'settings[0]' should be of type int"
    assert(type(settings[1]) == int), "Argument 'settings[1]' should be of type int"
    assert(type(settings[2]) == int), "Argument 'settings[2]' should be of type int"

    assert(type(settings[3]) == int), "Argument 'settings[3]' should be of type int"
    assert(type(settings[4]) == int), "Argument 'settings[4]' should be of type int"
    assert(type(settings[5]) == int), "Argument 'settings[5]' should be of type int"
    assert(type(settings[6]) == int), "Argument 'settings[6]' should be of type int"
    assert(type(settings[7]) == int), "Argument 'settings[7]' should be of type int"
    assert(type(settings[8]) == int), "Argument 'settings[8]' should be of type int"
    
    assert(type(settings[9]) in [int, float]), "Argument 'settings[9]' should be of type int or float"
    assert(type(settings[10]) in [int, float]), "Argument 'settings[10]' should be of type int or float"
    assert(type(settings[11]) in [int, float]), "Argument 'settings[11]' should be of type int or float"
    assert(type(settings[12]) in [int, float]), "Argument 'settings[12]' should be of type int or float"
    assert(type(settings[13]) in [int, float]), "Argument 'settings[13]' should be of type int or float"

    assert(type(settings[14]) in [pf.DataObject, type(None)]), "Argument 'settings[14]' should be of type powerfactory.DataObject"
    if(type(settings[14]) == pf.DataObject):
        assert(settings[14].GetClassName() == "ElmRes"), "Argument 'settings[14]' should be of class 'ElmRes'"
    assert(type(settings[15]) == int), "Argument 'settings[15]' should be of type int"
    assert(type(settings[16]) == str), "Argument 'settings[16]' should be of type str"
    assert(type(settings[17]) == int), "Argument 'settings[17]' should be of type int"

    # set the recording of eigen vectors to 1 (active)
    oComMod.ileft = settings[0]       #Controllability
    oComMod.iright = settings[1]      #Observability
    oComMod.iPart = settings[2]       #Participation factors

    # mark the boxes for boundry conditions
    oComMod.isRecOscModesOnly = settings[3]
    oComMod.isRecMinReal = settings[4]
    oComMod.isRecMinImag = settings[5]
    oComMod.isRecMaxReal = settings[6]
    oComMod.isRecMaxImag = settings[7]
    oComMod.isRecMaxDmapRat = settings[8]

    # set boundry conditions
    oComMod.minReal = settings[9]
    oComMod.minDampedFreq = settings[10]
    oComMod.maxReal = settings[11]
    oComMod.maxDampedFreq = settings[12]
    oComMod.maxDampRat = settings[13]

    #set params for exp file
    if not(settings[14] == None):
        oComRes.pResult = settings[14]
        oComRes.iopt_exp = settings[15]
        oComRes.f_name = settings[16]

    #set output type
    oComMod.outputType = settings[17]

def SSSANormal(app: pf.Application, sSSSAGenMon: list, settings: list, temp_SSSA: str):
    '''
    This funciton runs small signa stability assessment using the QR decomposition method.
    The Arguments of the functions are:\n

    app - The powerfactory application in which the desired project should already be activated.\n
    sSSSAGenMin - The list of generators who are to be monitored for SSSA.\n
    settings - The settings used for small signal stability assessments:\n
        - [0] minimal real values to be recorded\n
        - [1] maximal real values to be recorded\n
        - [2] minimum Damping frequency to be recorded\n
        - [3] maximum Damping frequency to be recorded\n
    temp_SSSA - The file location where temporary SSSA results (results from PF calculations) should be saved.
    '''

    oComMod = app.GetFromStudyCase("ComMod")
    oResExp = app.GetFromStudyCase("ComRes")

    #Get names of generators that need to be considered when running SSSA
    oComMod.Execute()
    Gen_record_SSSA = []
    for oGen in sSSSAGenMon:
        oGenName = oGen.GetAttribute("loc_name")
        Gen_record_SSSA.append(oGenName)
    userSettings = setUserParams(oComMod, oResExp, settings[0], settings[1], settings[2], settings[3], settings[4], settings[5], settings[6], settings[7], temp_SSSA)

    oComMod.Execute()
    oResExp.Execute()

    setInitialParams(oComMod, oResExp, userSettings)

    return(Gen_record_SSSA)

