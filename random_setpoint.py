'''
Author: Matjaz Skrlec
date: xx. xx. 20xx
version: x.x
description: This is the description of some code
'''

#--------------------------------------------------------------------------------------------------
## imports
import os
import sys
sys.path.append(os.getenv("PowerfactoryPyFilePath"))
import powerfactory as pf
import PFSupport.GetElements as GetElements
from typing import Literal
import random
import numpy as np
# -------------------------------------------------------------------------------------------------
## classes
# -------------------------------------------------------------------------------------------------
## functions
#--------------------------------------------------------------------------------------------------
## files used in code
#--------------------------------------------------------------------------------------------------
## variable parameters of code
#--------------------------------------------------------------------------------------------------
## code

def set_random_outed_elements(app: pf.Application, ElmType: Literal["ElmSym", "ElmLne", "ElmLod", "ElmTerm", "ElmTr2", "ElmTr3"], mode: Literal["exactly", "at_most"] = "exactly", n_elements: int = 0, iprint: bool = False) -> bool:
    '''
    Randomly set outserv of elements that have outerv at 0 to 1.

    :param app: The PowerFactory application object with the desired project activated.
    :param ElmType: Type of elements to be outed. Available are:
        -'ElmSym' for Synchronous machines
        -'ElmLne' for lines
        -'ElmLod' for loads
        -'ElmTerm' for terminals
        -'ElmTr2' for 2 winding transformers
        -'ElmTr3' for 3 winding transofrmers
    :param mode: Mode for number of outed elements. Available are:
        -'exactly' for exactly as manys as 'n_elements' elements are outed.
        -'at_most' for at_most as 'n_elements' elements are outed. The number is generated randomly.
    :param n_elements: The number of elements to be outed. Has to be integer.
    :param iprint: Should additional information be printed? [True, False]. Default is False.
    '''
    if ElmType not in ("ElmSym", "ElmLne", "ElmLod", "ElmTerm", "ElmTr2", "ElmTr3"):
        raise ValueError(f"Invalid ElmType: {ElmType}")
    
    if mode not in ("exactly", "at_most"):
        raise ValueError(f"Invalid mode: {mode}")
    assert(isinstance(n_elements, int)), "'n_elements' is not an integer."
    assert(isinstance(iprint, bool)), "'iprint' is not a bool."


    sElm = GetElements.GetElements(app, ElmType, ["outserv", 0])

    len_sElm = len(sElm)
    if len_sElm < n_elements:
        print("WARNING: The number set to 'n_elements' is greater than the number of active elements defined by 'ElmType'.")

    final_n_elements = n_elements
    if mode == "at_most":
        final_n_elements = random.randint(0,n_elements)

    if len_sElm <= n_elements:
        print("WARNING: number of elements to put out of service is greater than the number of in service elements. Outing all elements.")
        for oElm in sElm:
            oElm.SetAttribute("outserv", 1)
    else:
        selected_sElm = random.sample(sElm, final_n_elements)
        for oElm in selected_sElm:
            oElm.SetAttribute("outserv", 1)
        if iprint:
            match final_n_elements:
                case 0:
                    print(f"No element of type '{ElmType}' was put out of service.")
                case 1:
                    print(f"{final_n_elements} element of type '{ElmType}' was put out of service. Namely:")
                case _:
                    print(f"{final_n_elements} elements of type '{ElmType}' were put out of service. Namely:")
            for oElm in selected_sElm:
                oElm_name = oElm.GetAttribute("loc_name")
                print(f"{oElm_name}")

    return(True)

def set_random_gen_setpoint(oElm: pf.DataObject, select_parameter: Literal["P", "Q", "PQ"], p_setpoint_mean:float = 10, q_setpoint_mean:float = 10, p_setpoint_n_std: float = 0.1, q_setpoint_n_std = 0.1) -> bool:
    '''
    Randomly set the setpoint of a synchrnous machine, based on a beta distribution.

    :param oElm: The powerfactory element object whose setpoint is to be decided.
    :param select_parameter: Select which parameter to be set. Available are:
        - 'P' the active power (parameter 'pgini' is set)
        - 'Q' the reactive power (parameter 'qgini' is set)
        - 'PQ' the active and reactive power (parameters 'p_gini' and 'q_gini' are set)
    :param p_setpoint_mean: The mean of the normal distribution that decides P. 10 by default.
    :param q_setpoint_mean: The mean of the normal distribution that decides Q. 10 by defualt.
    :param p_setpoint_n_std: The normalised standard deviation based on the rated generators power (p_setpoint_n_std = p_std/Sn). 0.1 by default.
    :param q_setpoint_n_std: The normalised standard deviation based on the rated generators power (q_setpoint_n_std = q_std/Sn). 0.1 by default.
    '''
    if select_parameter not in ("P", "Q", "PQ"):
        raise ValueError(f"Invalid ElmType: {select_parameter}")
    assert(isinstance(p_setpoint_mean, (int, float))), "parameter 'p_setpoint_mean' must be a number"
    assert(isinstance(q_setpoint_mean, (int, float))), "parameter 'q_setpoint_mean' must be a number"
    assert(isinstance(p_setpoint_n_std, (int, float))), "parameter 'p_setpoint_n_std' must be a number"
    assert(isinstance(q_setpoint_n_std, (int, float))), "parameter 'p_setpoint_mean' must be a number"
    assert(isinstance(oElm, pf.DataObject)), "parameter 'oElm' must be a powerfactory object"

    oTypSym = oElm.GetAttribute("typ_id")

    if not oTypSym:
        print(f"Given object {oElm} does not have a 'type_id' parameter. Not setting random power value.")
        return(False)
    Sn = oTypSym.GetAttribute("sgn")

    if select_parameter in ("P", "PQ"):
        if not 0 < p_setpoint_mean < Sn:
            print(f"Parameter 'p_setpoint_mean' should be greater than 0 and smaller than the rater power of the generator. Not setting P.")
            print(oElm)
            print(p_setpoint_mean)
            print(Sn)
        else:
            p_m = p_setpoint_mean/Sn
            p_s = p_setpoint_n_std
            p_k = p_m * (1-p_m) / p_s**2 -1
            p_alpha = p_m * p_k
            p_beta = (1-p_m) * p_k

            new_p_setpoint = Sn * np.random.beta(p_alpha, p_beta)

            oElm.SetAttribute("pgini", new_p_setpoint)

    if select_parameter in ("Q", "PQ"):
        if not -Sn < q_setpoint_mean < Sn:
            print(f"Parameter 'q_setpoint_mean' should be greater than the negative reted power and smaller than the rater power of the generator. Not setting Q.")
            print(oElm)
            print(p_setpoint_mean)
            print(Sn)
        else:
            q_width = 2*Sn
            q_m = (q_setpoint_mean+Sn)/q_width
            q_s = q_setpoint_n_std
            q_k = q_m * (1-q_m) / q_s**2 -1
            q_alpha = q_m * q_k
            q_beta = (1-q_m) * q_k

            new_q_setpoint = -Sn + q_width * np.random.beta(q_alpha, q_beta)

            oElm.SetAttribute("qgini", new_q_setpoint)

def set_random_lod_setpoint(oElm: pf.DataObject, select_parameter: Literal["P", "Q", "PQ"], p_setpoint_mean:float = 10, q_setpoint_mean:float = 10, p_setpoint_n_std: float = 0.1, q_setpoint_n_std = 0.1, p_setpoint_u_lim:float = 100, q_setpoint_bounds:list = [-100,100]) -> bool:
    '''
    Randomly set the setpoint of a synchrnous machine, based on a beta distribution.

    :param oElm: The powerfactory element object whose setpoint is to be decided.
    :param select_parameter: Select which parameter to be set. Available are:
        - 'P' the active power (parameter 'pgini' is set)
        - 'Q' the reactive power (parameter 'qgini' is set)
        - 'PQ' the active and reactive power (parameters 'p_gini' and 'q_gini' are set)
    :param p_setpoint_mean: The mean of the normal distribution that decides P. 10 by default.
    :param q_setpoint_mean: The mean of the normal distribution that decides Q. 10 by defualt.
    :param p_setpoint_n_std: The normalised standard deviation based on the rated generators power (p_setpoint_n_std = p_std/Sn). 0.1 by default.
    :param q_setpoint_n_std: The normalised standard deviation based on the rated generators power (q_setpoint_n_std = q_std/Sn). 0.1 by default.
    :param p_setpoint_u_lim: The upper limit of the loads active power.
    :param q_setpoint_bounds: The tuple or list, containing the lower and upper limits of the load reactive power.
    '''
    if select_parameter not in ("P", "Q", "PQ"):
        raise ValueError(f"Invalid ElmType: {select_parameter}")
    assert(isinstance(p_setpoint_mean, (int, float))), "parameter 'p_setpoint_mean' must be a number"
    assert(isinstance(q_setpoint_mean, (int, float))), "parameter 'q_setpoint_mean' must be a number"
    assert(isinstance(p_setpoint_n_std, (int, float))), "parameter 'p_setpoint_n_std' must be a number"
    assert(isinstance(q_setpoint_n_std, (int, float))), "parameter 'p_setpoint_mean' must be a number"
    assert(isinstance(p_setpoint_u_lim, (int, float))), "parameter 'p_setpoind_bounds' must be a number"
    assert(isinstance(q_setpoint_bounds, (tuple, list))), "parameter 'q_setpoind_bounds' must be tuple or list."
    assert(isinstance(oElm, pf.DataObject)), "parameter 'oElm' must be a powerfactory object"
    if len(q_setpoint_bounds) != 2:
        raise ValueError(f"q_setpoint_bounds must be of length 2.")

    if select_parameter in ("P", "PQ"):
        if not 0 < p_setpoint_mean < p_setpoint_u_lim:
            print(f"Parameter 'p_setpoint_mean' should be greater than 0 and smaller than the 'p_setpoint_u_lim'. Not setting P.")
        else:
            p_m = p_setpoint_mean/p_setpoint_u_lim
            p_s = p_setpoint_n_std
            p_k = p_m * (1-p_m) / p_s**2 -1
            p_alpha = p_m * p_k
            p_beta = (1-p_m) * p_k

            new_p_setpoint = p_setpoint_u_lim * np.random.beta(p_alpha, p_beta)

            oElm.SetAttribute("plini", new_p_setpoint)

    if select_parameter in ("Q", "PQ"):
        q_setpoint_l_lim = q_setpoint_bounds[0]
        q_setpoint_u_lim = q_setpoint_bounds[1]
        if not q_setpoint_l_lim < q_setpoint_mean < q_setpoint_u_lim:
            print(f"Parameter 'q_setpoint_mean' should be greater than the negative reted power and smaller than the rated power of the load. Not setting Q.")
            print(oElm)
            print(q_setpoint_l_lim)
            print(q_setpoint_mean)
            print(q_setpoint_u_lim)
        else:
            q_width = q_setpoint_u_lim - q_setpoint_l_lim
            q_m = (q_setpoint_mean - q_setpoint_l_lim)/q_width
            q_s = q_setpoint_n_std
            q_k = q_m * (1-q_m) / q_s**2 -1
            q_alpha = q_m * q_k
            q_beta = (1-q_m) * q_k

            new_q_setpoint = q_setpoint_l_lim + q_width * np.random.beta(q_alpha, q_beta)

            oElm.SetAttribute("qlini", new_q_setpoint)

def set_random_setpoint_operation_state(app: pf.Application, set_gen_random: bool = True, set_lod_random: bool = True, out_lines: bool = False, n_out_lines:int = 2) -> bool:
    '''
    Set a random power system setpoint for powerfactory elements.

    :param oElm: The powerfactory element object whose setpoint is to be decided.
    :param select_parameter: Select which parameter to be set. Available are:
        - 'P' the active power (parameter 'pgini' is set)
        - 'Q' the reactive power (parameter 'qgini' is set)
        - 'PQ' the active and reactive power (parameters 'p_gini' and 'q_gini' are set)
    :param p_setpoint_mean: The mean of the normal distribution that decides P. 10 by default.
    :param q_setpoint_mean: The mean of the normal distribution that decides Q. 10 by defualt.
    :param p_setpoint_n_std: The normalised standard deviation based on the rated generators power (p_setpoint_n_std = p_std/Sn). 0.1 by default.
    :param q_setpoint_n_std: The normalised standard deviation based on the rated generators power (q_setpoint_n_std = q_std/Sn). 0.1 by default.
    :param p_setpoint_u_lim: The upper limit of the loads active power.
    :param q_setpoint_bounds: The tuple or list, containing the lower and upper limits of the load reactive power.
    '''
    #initial generator and load power values [loc_name,P,Q]
    Gen_values = [["G 01",500,0],["G 04",265,0],["G 05",100,0],["G 07",230,0],["G 08",230,0],["G 10",330,0]]

    Load_values = [["Load 03",111,1.2],["Load 04",200,9.2],["Load 07",116.9,42],["Load 08",261,88],["Load 12",3.75,44],["Load 15",160,76.5],
                ["Load 16",164.5,16.15],["Load 18",79,15],["Load 20",314,51.5],["Load 21",112,57.5],["Load 23",123.75,42.3],["Load 24",154.3,-46.1],
                ["Load 25",112,23.6],["Load 26",69.5,8.5],["Load 27",140.5,37.75],["Load 28",103,13.8],["Load 29",141.75,13.45],["Load 31",4.6,2.3],
                ["Load 39",552,125]]

    assert(isinstance(app, pf.Application)), "parameter 'app' must be powefactory.Applicaiton"
    assert(isinstance(set_gen_random, bool)), "parameter 'set_gen_random' must be a bool"
    assert(isinstance(set_lod_random, bool)), "parameter 'set_lod_random' must be a bool"
    assert(isinstance(out_lines, bool)), "parameter 'out_lines' must be a bool"
    assert(isinstance(n_out_lines, int)), "parameter 'n_out_lines' must be an integer"

    # Get project objects
    sElmSym = app.GetCalcRelevantObjects("*.ElmSym")
    sElmLod = app.GetCalcRelevantObjects("*.ElmLod")
    #loading level using uniform distribution
    loading_factor = np.random.uniform(0.5,2.75)

    if set_gen_random:
        for oElmSym in sElmSym:
            for Gen_value in Gen_values:
                if Gen_value[0] in oElmSym.GetAttribute("loc_name"):
                    new_p_mean = Gen_value[1] * loading_factor
                    new_q_mean = Gen_value[2] * loading_factor
                    set_random_gen_setpoint(oElmSym, 'P', new_p_mean, new_q_mean, 0.05, 0.05)

    if set_lod_random:
        for oElmLod in sElmLod:
            for Load_value in Load_values:
                if Load_value[0] in oElmLod.GetAttribute("loc_name"):
                    new_p_mean = Load_value[1] * loading_factor
                    new_q_mean = Load_value[2] * loading_factor
                    new_p_max = new_p_mean*2
                    if new_q_mean >= 0:
                        new_q_max = new_q_mean*2
                        new_q_min = -new_q_max
                    else:
                        new_q_min = new_q_mean*2
                        new_q_max = -new_q_min
                    set_random_lod_setpoint(oElmLod, 'PQ',new_p_mean, new_q_mean, 0.05, 0.05, new_p_max, [new_q_min, new_q_max])

    if out_lines:
        set_random_outed_elements(app, 'ElmLne', 'at_most', n_out_lines)

    return(True)