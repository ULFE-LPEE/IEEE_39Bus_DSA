'''
Author: Matjaz Skrlec
date: 07. 02. 2024
version: 1.0
description: This is the module for manipulating elements in powerfactory
'''

#--------------------------------------------------------------------------------------------------
## imports
import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.getenv("PowerfactoryPyFilePath"))
import powerfactory as pf
from collections.abc import Iterable
import logging

def EvalStatement(oElm, Attributes, mode, andor, n):
    if n == len(Attributes):
        if andor == "and":
            return(True)
        if andor == "or":
            return(False)

    if andor == 'and':
        currEval = Attributes[n]
        currMode = mode[n]
        if currMode == "eval":
            result = (oElm.GetAttribute(currEval[0])) == currEval[1]
        if currMode == "min":
            result = (oElm.GetAttribute(currEval[0])) > currEval[1]
        if currMode == "max":
            result = (oElm.GetAttribute(currEval[0])) < currEval[1]
        if currMode == "absmin":
             result = abs(oElm.GetAttribute(currEval[0])) > currEval[1]
        if currMode == "absmax":
             result = abs(oElm.GetAttribute(currEval[0])) < currEval[1]
        if not result:
            return False
        n += 1
        Eval = EvalStatement(oElm, Attributes, mode, andor, n)
        return(Eval)
        
    if andor == 'or':
        currEval = Attributes[n]
        currMode = mode[n]
        if currMode == "eval":
            result = (oElm.GetAttribute(currEval[0])) == currEval[1]
        if currMode == "min":
            result = (oElm.GetAttribute(currEval[0])) > currEval[1]
        if currMode == "max":
            result = (oElm.GetAttribute(currEval[0])) < currEval[1]
        if currMode == "absmin":
             result = abs(oElm.GetAttribute(currEval[0])) > currEval[1]
        if currMode == "absmax":
             result = abs(oElm.GetAttribute(currEval[0])) < currEval[1]
        if result:
            return True
        n += 1
        Eval = EvalStatement(oElm, Attributes, mode, andor, n)
        return(Eval)



def EnableElm(sElm: list | pf.DataObject, Attributes: list =[] ,  mode = "eval", andor = "and"):
    '''
    This function enables elements if their Attributes meet a certain comdition. An element or a list/tuple of elements may be passed.
    The Attributes and the values to be checked are given with the argument 'Attributes' as lists/tuples of attribute/value pairs.
    If the Attribute is a floting point value, the mode for evaluation can be specified with argument 'mode':
    mode = "eval" (default), evaluetes if the attribute is equal to the value given and enabels it if True,
    mode = "min", evalueates if the attribute is higher than the argument 'AttValue' and enables it if True,
    mode = "max", evalueates if the attribute is lower than the argument 'AttValue' and enabels it if True,
    mode = "absmin", evaluates if the absolute value of the attribute is higher than the atgument 'AttValue' and enables it if True,
    mode = "absmax", evaluates if the absolute value of the attribute is lower than the argument 'AttValue' and enables it if True.
    If multiple Attributes are passed, the mode for each Attribute can be specified, by passing a list/tuple to the mode argument.
    If multiple Attributes are passed, the exclusion between arguments can be specified with argument 'andor':
    andor = "and" (default), all arguments have to be met to enable the object, 
    andor = "or", if one argument is met, the object is enabled
    The elements that have been enabled are returned
    '''

    if type(sElm) != pf.DataObject:
        assert(type(sElm) in [list, tuple]), "Argument 'sElm' should be of type list, tuple or powerfactory.DataObject"
        for i in range(len(sElm)):
            assert(type(sElm[i]) == pf.DataObject), f"Argument 'sElm[{i}]' should be of type powerfactory.DataObject"
    assert(type(Attributes) in [list, tuple]), "Argument 'Attributes' should be of type list or tuple."

    if len(Attributes) == 1:
        assert(len(Attributes[0]) == 2), "Argument 'Attributes [0]' should have two inputs."
        assert(type(Attributes[0][0]) == str), "Argument 'Attributes [0][0]' should be string."
        assert(type(mode) in [str, list, tuple]), "Argument 'mode' should be string or list/tuple with one entry"
        if type(mode) == str:
            assert(mode in ["eval", "min", "max", "absmin", "absmax"]), "Argument 'mode' should be one of 'eval', 'min', 'max', 'absmin' or 'absmax'."
            if mode in ["min", "max", "absmin", "absmax"]:
                assert(type(Attributes[0][1]) in [int, float]), "Argument 'Attributes[0][1]' should be int or float if 'mode' is 'min', 'max', 'absmin' or 'absmax'."
        else:
            assert(len(mode) == 1), "Argument 'mode' should only have one entry."
            assert(mode[0] in ["eval", "min", "max", "absmin", "absmax"]), "Argument 'mode[0]' should be one of 'eval', 'min', 'max', 'absmin' or 'absmax'."
            if mode[0] in ["min", "max", "absmin", "absmax"]:
                assert(type(Attributes[0][1]) in [int, float]), "Argument 'Attributes[0][1]' should be int or float if 'mode[0]' is 'min', 'max', 'absmin' or 'absmax'."

    elif len(Attributes) == 2:
        if type(Attributes[0]) in [list, tuple]:
            assert(len(mode) == 2), "Argument mode should have 2 entries."
            for i in range(len(Attributes)):
                assert(len(Attributes[i]) == 2), f"Argument 'Attributes [{i}]' should have 2 entries."
                assert(type(Attributes[i][0]) == str), f"Argument 'Attributes [{i}][0]' should be string."
                assert(mode[i] in ["eval", "min", "max", "absmin", "absmax"]), f"Argument 'mode[i]' should be one of 'eval', 'min', 'max', 'absmin' or 'absmax'."
                if mode[i] in ["min", "max", "absmin", "absmax"]:
                    assert(type(Attributes[i][1]) in [int, float]), f"Argument 'Attributes[{i}][1]' should be int or float if 'mode[{i}]' is 'min', 'max', 'absmin' or 'absmax'."
                
        else:
            assert(type(mode) in [str, list, tuple]), "Argument 'mode' should be string or list/tuple with one entry"
            assert(type(Attributes[0]) == str), "Argument 'Attributes [0]' should be string."
            if type(mode) == str:
                assert(mode in ["eval", "min", "max", "absmin", "absmax"]), "Argument 'mode' should be one of 'eval', 'min', 'max', 'absmin' or 'absmax'."
                if mode in ["min", "max", "absmin", "absmax"]:
                    assert(type(Attributes[0][1]) in [int, float]), "Argument 'Attributes[0][1]' should be int or float if 'mode' is 'min', 'max', 'absmin' or 'absmax'."
            else:
                assert(len(mode) == 1), "Argument 'mode' should only have one entry."
                assert(mode[0] in ["eval", "min", "max", "absmin", "absmax"]), "Argument 'mode[0]' should be one of 'eval', 'min', 'max', 'absmin' or 'absmax'."
                if mode[0] in ["min", "max", "absmin", "absmax"]:
                    assert(type(Attributes[0][1]) in [int, float]), "Argument 'Attributes[0][1]' should be int or float if 'mode[0]' is 'min', 'max', 'absmin' or 'absmax'."
    
    else:
        assert(len(Attributes) == len(mode)), "Arguments 'Attributes' and 'mode' should be the same size."
        for i in range(2, len(Attributes)):
            assert(len(Attributes[i]) == 2), f"Argument 'Attributes [{i}] should have 2 entries."
            assert(type(Attributes[i][0]) == str), f"Argument 'Attributes [{i}][0] should be string"
            assert(mode[i] in ["eval", "min", "max", "absmin", "absmax"]), f"Argument 'mode[i]' should be one of 'eval', 'min', 'max', 'absmin' or 'absmax'."
            if mode[i] in ["min", "max", "absmin", "absmax"]:
                assert(type(Attributes[i][1]) in [int, float]), f"Argument 'Attributes[{i}][1]' should be int or float if 'mode[{i}]' is 'min', 'max', 'absmin' or 'absmax'."

    retElm = []
    if sElm != pf.DataObject:
        for oElm in sElm:
            if EvalStatement(oElm, Attributes, mode, andor, 0):
                oElm.SetAttribute("outserv", 0)
                retElm.append(oElm)
    
    else:
        if EvalStatement(sElm, Attributes, mode, andor, 0):
            sElm.SetAttribute("outserv", 0)
            retElm = oElm

    return(retElm)




def DisableElm(sElm: list | pf.DataObject, Attributes: list =[] ,  mode = "eval", andor = "and"):
    '''
    This function disables elements if their Attributes meet a certain comdition. An element or a list/tuple of elements may be passed.
    The Attributes and the values to be checked are given with the argument 'Attributes' as lists/tuples of attribute/value pairs.
    If the Attribute is a floting point value, the mode for evaluation can be specified with argument 'mode':
    mode = "eval" (default), evaluetes if the attribute is equal to the value given and enabels it if True,
    mode = "min", evalueates if the attribute is higher than the argument 'AttValue' and enables it if True,
    mode = "max", evalueates if the attribute is lower than the argument 'AttValue' and enabels it if True,
    mode = "absmin", evaluates if the absolute value of the attribute is higher than the atgument 'AttValue' and enables it if True,
    mode = "absmax", evaluates if the absolute value of the attribute is lower than the argument 'AttValue' and enables it if True.
    If multiple Attributes are passed, the mode for each Attribute can be specified, by passing a list/tuple to the mode argument.
    If multiple Attributes are passed, the exclusion between arguments can be specified with argument 'andor':
    andor = "and" (default), all arguments have to be met to disable the object, 
    andor = "or", if one argument is met, the object is disabled
    '''

    if type(sElm) != pf.DataObject:
        assert(type(sElm) in [list, tuple]), "Argument 'sElm' should be of type list, tuple or powerfactory.DataObject"
        for i in range(len(sElm)):
            assert(type(sElm[i]) == pf.DataObject), f"Argument 'sElm[{i}]' should be of type powerfactory.DataObject"
    assert(type(Attributes) in [list, tuple]), "Argument 'Attributes' should be of type list or tuple."

    if len(Attributes) == 1:
        assert(len(Attributes[0]) == 2), "Argument 'Attributes [0]' should have two inputs."
        assert(type(Attributes[0][0]) == str), "Argument 'Attributes [0][0]' should be string."
        assert(type(mode) in [str, list, tuple]), "Argument 'mode' should be string or list/tuple with one entry"
        if type(mode) == str:
            assert(mode in ["eval", "min", "max", "absmin", "absmax"]), "Argument 'mode' should be one of 'eval', 'min', 'max', 'absmin' or 'absmax'."
            if mode in ["min", "max", "absmin", "absmax"]:
                assert(type(Attributes[0][1]) in [int, float]), "Argument 'Attributes[0][1]' should be int or float if 'mode' is 'min', 'max', 'absmin' or 'absmax'."
        else:
            assert(len(mode) == 1), "Argument 'mode' should only have one entry."
            assert(mode[0] in ["eval", "min", "max", "absmin", "absmax"]), "Argument 'mode[0]' should be one of 'eval', 'min', 'max', 'absmin' or 'absmax'."
            if mode[0] in ["min", "max", "absmin", "absmax"]:
                assert(type(Attributes[0][1]) in [int, float]), "Argument 'Attributes[0][1]' should be int or float if 'mode[0]' is 'min', 'max', 'absmin' or 'absmax'."

    elif len(Attributes) == 2:
        if type(Attributes[0]) in [list, tuple]:
            assert(len(mode) == 2), "Argument mode should have 2 entries."
            for i in range(len(Attributes)):
                assert(len(Attributes[i]) == 2), f"Argument 'Attributes [{i}]' should have 2 entries."
                assert(type(Attributes[i][0]) == str), f"Argument 'Attributes [{i}][0]' should be string."
                assert(mode[i] in ["eval", "min", "max", "absmin", "absmax"]), f"Argument 'mode[i]' should be one of 'eval', 'min', 'max', 'absmin' or 'absmax'."
                if mode[i] in ["min", "max", "absmin", "absmax"]:
                    assert(type(Attributes[i][1]) in [int, float]), f"Argument 'Attributes[{i}][1]' should be int or float if 'mode[{i}]' is 'min', 'max', 'absmin' or 'absmax'."
                
        else:
            assert(type(mode) in [str, list, tuple]), "Argument 'mode' should be string or list/tuple with one entry"
            assert(type(Attributes[0]) == str), "Argument 'Attributes [0]' should be string."
            if type(mode) == str:
                assert(mode in ["eval", "min", "max", "absmin", "absmax"]), "Argument 'mode' should be one of 'eval', 'min', 'max', 'absmin' or 'absmax'."
                if mode in ["min", "max", "absmin", "absmax"]:
                    assert(type(Attributes[0][1]) in [int, float]), "Argument 'Attributes[0][1]' should be int or float if 'mode' is 'min', 'max', 'absmin' or 'absmax'."
            else:
                assert(len(mode) == 1), "Argument 'mode' should only have one entry."
                assert(mode[0] in ["eval", "min", "max", "absmin", "absmax"]), "Argument 'mode[0]' should be one of 'eval', 'min', 'max', 'absmin' or 'absmax'."
                if mode[0] in ["min", "max", "absmin", "absmax"]:
                    assert(type(Attributes[0][1]) in [int, float]), "Argument 'Attributes[0][1]' should be int or float if 'mode[0]' is 'min', 'max', 'absmin' or 'absmax'."
    
    else:
        assert(len(Attributes) == len(mode)), "Arguments 'Attributes' and 'mode' should be the same size."
        for i in range(2, len(Attributes)):
            assert(len(Attributes[i]) == 2), f"Argument 'Attributes [{i}] should have 2 entries."
            assert(type(Attributes[i][0]) == str), f"Argument 'Attributes [{i}][0] should be string"
            assert(mode[i] in ["eval", "min", "max", "absmin", "absmax"]), f"Argument 'mode[i]' should be one of 'eval', 'min', 'max', 'absmin' or 'absmax'."
            if mode[i] in ["min", "max", "absmin", "absmax"]:
                assert(type(Attributes[i][1]) in [int, float]), f"Argument 'Attributes[{i}][1]' should be int or float if 'mode[{i}]' is 'min', 'max', 'absmin' or 'absmax'."

    retElm = []
    if sElm != pf.DataObject:
        for oElm in sElm:
            eval = EvalStatement(oElm, Attributes, mode, andor, 0)
            if eval:
                oElm.SetAttribute("outserv", 1)
                retElm.append(oElm)
    
    else:
        if EvalStatement(sElm, Attributes, mode, andor, 0):
            sElm.SetAttribute("outserv", 1)
            retElm.append(oElm)

    return(retElm)

def DisableIsolatedElements(RefElement: pf.DataObject, ConsideredElements: list[pf.DataObject]):
    '''
    Puts all elements in 'ConsideredElements' that are not in same reagion as 'RedElement' out of service.
    '''

    assert(isinstance(RefElement, pf.DataObject)), "Object 'RefElement' is not of type powerfactory.DataObject"
    assert(isinstance(ConsideredElements, Iterable)), "Object 'ConsideredElements' is not an Iterable"
    for ind, oElm in enumerate(ConsideredElements):
        assert(isinstance(oElm, pf.DataObject)), f"Object 'ConsideredElements[{ind}]' is not of type powerfactory.DataObject"

    ReferenceRegion = RefElement.GetRegion()
    for oElm in ConsideredElements:
        if oElm.GetRegion() != ReferenceRegion:
            oElmName = oElm.GetAttribute("loc_name")
            RefElmName = RefElement.GetAttribute("loc_name")
            if oElm.GetAttribute("outserv") == 0:
                
                print(f"ReferenceRegion: {ReferenceRegion}, ElementRegion: {oElm.GetRegion()}")
                print(f"Disbaling element {oElmName}, because it is not in same region as element {RefElmName}.")
                logging.info(f"Disbling element {oElmName}, because it is not in same region as element {RefElmName}.")
                oElm.SetAttribute("outserv", 1)
    
    return True