'''
Author: Matjaz Skrlec
date: 20. 03. 2026
version: 1.0
description: This module is used for some basic creation of elements.
'''

def CreateBlkDef(name: str, folder):
    
    '''This function creates a model type in the designated folder'''

    assert type(name) == str, "name should be string not "+ str(type(name))
    assert folder.GetClassName() in ["IntFolder","IntPrjfolder"], "Given folder is not folder."

    return(folder.CreateObject("BlkDef",name))