'''
Author: Matjaz Skrlec
date: 07. 02. 2024
version: 1.0
description: This is the module for basic powerfactory routines
'''

#--------------------------------------------------------------------------------------------------
## imports
import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.getenv("PowerfactoryPyFilePath"))
import powerfactory as pf
import random
from collections.abc import Iterable

def ElmFilter(sElm: list, AttName: str, AttValue):
    FilLst = []
    for i in sElm:
        if isinstance(AttValue, Iterable) and not isinstance(AttValue, (str, bytes)):
            if i.GetAttribute(AttName) in AttValue:
                FilLst.append(i)
        else:
            if i.GetAttribute(AttName) == AttValue:
                FilLst.append(i)
    return (FilLst)

def GetElements(app: pf.Application, Class: str, Attributes: list = [], num = None, rand = False):
    '''
    This function returns a list of elements of the class given with 'Class'. Optionally a list/tuple of lists/tuples can be given 
    with argument "Attributes" to filter through the elements with specific attributes. The inner lists/tuples should have two entries.
    The 1st entry is the name of the attribute to be filtered by, the 2nd entry is the value of the attribute to filter by.
    '''
    assert(type(app) == pf.Application), "Argument 'app' is not of type powerfactory.Application."
    
    if Attributes:
        assert(type(Attributes) in [list, tuple]), "Argument 'Attributes' should be of type list or tuple."
        if len(Attributes) == 1:
            assert(len(Attributes[0]) == 2), "Argument 'Attributes [0]' should have two inputs."
            assert(type(Attributes[0][0]) == str), "Argument 'Attributes [0][0]' should be string."
        elif len(Attributes) == 2:
            if type(Attributes[0]) in [list, tuple]:
                for i in range(len(Attributes)):
                    assert(len(Attributes[i]) == 2), f"Argument 'Attributes [{i}]' should have 2 entries."
                    assert(type(Attributes[i][0]) == str), f"Argument 'Attributes [{i}][0]' should be string."
            else:
                assert(type(Attributes[0]) == str), "Argument 'Attributes [0]' should be string."
        else:
            for i in range(2, len(Attributes)):
                assert(len(Attributes[i]) == 2), f"Argument 'Attributes [{i}] should have 2 entries."
                assert(type(Attributes[i][0]) == str), f"Argument 'Attributes [{i}][0] should be string"

    if num:
        assert(type(num) == int), "Argument 'num' should be intiger"

    assert(rand in [True, False]), "Argument 'rand' should only be True or False"
    
    sElm = app.GetCalcRelevantObjects("*."+Class)

    if Attributes:
        if len(Attributes) == 2:
            if type(Attributes[0]) == str:
                sElm = ElmFilter(sElm, Attributes[0], Attributes[1])
            else:
                for AttIt in Attributes:
                    sElm = ElmFilter(sElm, AttIt[0], AttIt[1])
        else:
            for AttIt in Attributes:
                sElm = ElmFilter(sElm, AttIt[0], AttIt[1])

    if num:
        if num < len(sElm):
            if rand:
                sElm = random.sample(sElm, num)
            else:
                sElm = sElm[:num]

    return(sElm)



