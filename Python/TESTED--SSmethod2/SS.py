'''
------------------------------------------------------------------------
Last updated: 6/4/2015

Calculates steady state of OLG model with S age cohorts.

This py-file calls the following other file(s):
            income.py
            demographics.py
            tax_funcs.py
            OUTPUT/given_params.pkl
            OUTPUT/Saved_moments/wealth_data_moments_fit_{}.pkl
                name depends on which percentile
            OUTPUT/Saved_moments/labor_data_moments.pkl
            OUTPUT/income_demo_vars.pkl
            OUTPUT/Saved_moments/{}.pkl
                name depends on what iteration just ran
            OUTPUT/SS/d_inc_guess.pkl
                if calibrating the income tax to match the wealth tax

This py-file creates the following other file(s):
    (make sure that an OUTPUT folder exists)
            OUTPUT/income_demo_vars.pkl
            OUTPUT/Saved_moments/{}.pkl
                name depends on what iteration is being run
            OUTPUT/Saved_moments/payroll_inputs.pkl
            OUTPUT/SSinit/ss_init.pkl
------------------------------------------------------------------------
'''

# Packages
import numpy as np
import os
import scipy.optimize as opt
import cPickle as pickle

import tax_funcs as tax
import household_funcs as house
import firm_funcs as firm
import misc_funcs


'''
------------------------------------------------------------------------
Imported user given values
------------------------------------------------------------------------
S            = number of periods an individual lives
J            = number of different ability groups
T            = number of time periods until steady state is reached
lambdas_init  = percent of each age cohort in each ability group
starting_age = age of first members of cohort
ending age   = age of the last members of cohort
E            = number of cohorts before S=1
beta         = discount factor for each age cohort
sigma        = coefficient of relative risk aversion
alpha        = capital share of income
nu_init      = contraction parameter in steady state iteration process
               representing the weight on the new distribution gamma_new
Z            = total factor productivity parameter in firms' production
               function
delta        = depreciation rate of capital for each cohort
ltilde       = measure of time each individual is endowed with each
               period
eta          = Frisch elasticity of labor supply
g_y          = growth rate of technology for one cohort
maxiter   = Maximum number of iterations that TPI will undergo
mindist   = Cut-off distance between iterations for TPI
b_ellipse    = value of b for elliptical fit of utility function
k_ellipse    = value of k for elliptical fit of utility function
slow_work    = time at which chi_n starts increasing from 1
mean_income_data  = mean income from IRS data file used to calibrate income tax
               (scalar)
a_tax_income = used to calibrate income tax (scalar)
b_tax_income = used to calibrate income tax (scalar)
c_tax_income = used to calibrate income tax (scalar)
d_tax_income = used to calibrate income tax (scalar)
tau_bq       = bequest tax (scalar)
tau_payroll  = payroll tax (scalar)
theta    = payback value for payroll tax (scalar)
retire       = age in which individuals retire(scalar)
h_wealth     = wealth tax parameter h
p_wealth     = wealth tax parameter p
m_wealth     = wealth tax parameter m
------------------------------------------------------------------------
'''

variables = pickle.load(open("OUTPUT/Saved_moments/params_given.pkl", "r"))
for key in variables:
    globals()[key] = variables[key]
if os.path.isfile("OUTPUT/Saved_moments/params_changed.pkl"):
    variables = pickle.load(open("OUTPUT/Saved_moments/params_changed.pkl", "r"))
    for key in variables:
        globals()[key] = variables[key]


'''
------------------------------------------------------------------------
    Define Functions
------------------------------------------------------------------------
'''

# Make a vector of all one dimensional parameters, to be used in the following functions
income_tax_params = [a_tax_income, b_tax_income, c_tax_income, d_tax_income]
wealth_tax_params = [h_wealth, p_wealth, m_wealth]
ellipse_params = [b_ellipse, upsilon]
parameters = [J, S, T, beta, sigma, alpha, Z, delta, ltilde, nu, g_y, tau_payroll, retire, mean_income_data] + income_tax_params + wealth_tax_params + ellipse_params
iterative_params = [maxiter, mindist]

# Functions


def Euler_equation_solver(guesses, r, w, T_H, factor, j, params, chi_b, chi_n, theta, tau_bq, rho, lambdas, weights):
    b_guess = np.array(guesses[:S])
    n_guess = np.array(guesses[S:])
    b_s = np.array([0] + list(b_guess[:-1]))
    b_splus1 = b_guess
    b_splus2 = np.array(list(b_guess[1:]) + [0])

    BQ = (1+r) * (b_guess * weights[:, j] * rho).sum()

    error1 = house.euler_savings_func(w, r, e[:, j], n_guess, b_s, b_splus1, b_splus2, BQ, factor, T_H, chi_b[j], params, theta[j], tau_bq[j], rho, lambdas[j])
    error2 = house.euler_labor_leisure_func(w, r, e[:, j], n_guess, b_s, b_splus1, BQ, factor, T_H, chi_n, params, theta[j], tau_bq[j], lambdas[j])
    # Put in constraints
    mask1 = n_guess < 0
    mask2 = n_guess > ltilde
    mask3 = b_guess <= 0
    error2[mask1] += 1e9
    error2[mask2] += 1e9
    error1[mask3] += 1e9
    tax1 = tax.total_taxes(r, b_s, w, e[:, j], n_guess, BQ, lambdas[j], factor, T_H, None, 'SS', False, params, theta[j], tau_bq[j])
    cons = house.get_cons(r, b_s, w, e[:, j], n_guess, BQ, lambdas[j], b_splus1, params, tax1)
    mask4 = cons < 0
    error1[mask4] += 1e9
    return list(error1.flatten()) + list(error2.flatten())


def new_SS_Solver(b_guess_init, n_guess_init, wguess, rguess, T_Hguess, factorguess, chi_n, chi_b, params, iterative_params, theta, tau_bq, rho, lambdas, weights):
    J, S, T, beta, sigma, alpha, Z, delta, ltilde, nu, g_y, tau_payroll, retire, mean_income_data, a_tax_income, b_tax_income, c_tax_income, d_tax_income, h_wealth, p_wealth, m_wealth, b_ellipse, upsilon = params
    maxiter, mindist = iterative_params
    w = wguess
    r = rguess
    T_H = T_Hguess
    factor = factorguess
    bssmat = b_guess_init
    nssmat = n_guess_init

    dist = 10
    iteration = 0
    dist_vec = np.zeros(maxiter)
    
    while (dist > mindist) and (iteration < maxiter):
        for j in xrange(J):
            # Solve the euler equations
            guesses = np.append(bssmat[:, j], nssmat[:, j])
            solutions = opt.fsolve(Euler_equation_solver, guesses * .9, args=(r, w, T_H, factor, j, params, chi_b, chi_n, theta, tau_bq, rho, lambdas, weights))
            bssmat[:,j] = solutions[:S]
            nssmat[:,j] = solutions[S:]
            # print np.array(Euler_equation_solver(np.append(bssmat[:, j], nssmat[:, j]), r, w, T_H, factor, j, params, chi_b, chi_n, theta, tau_bq, rho, lambdas)).max()

        K = house.get_K(bssmat, weights)
        L = firm.get_L(e, nssmat, weights)
        Y = firm.get_Y(K, L, params)
        new_r = firm.get_r(Y, K, params)
        new_w = firm.get_w(Y, L, params)
        b_s = np.array(list(np.zeros(J).reshape(1, J)) + list(bssmat[:-1, :]))
        average_income_model = ((new_r * b_s + new_w * e * nssmat) * weights).sum()
        new_factor = mean_income_data / average_income_model 
        new_BQ = (1+new_r)*(bssmat * weights * rho.reshape(S, 1)).sum(0)
        new_T_H = tax.get_lump_sum(new_r, b_s, new_w, e, nssmat, new_BQ, lambdas, factor, weights, 'SS', params, theta, tau_bq)

        r = misc_funcs.convex_combo(new_r, r, params)
        w = misc_funcs.convex_combo(new_w, w, params)
        factor = misc_funcs.convex_combo(new_factor, factor, params)
        T_H = misc_funcs.convex_combo(new_T_H, T_H, params)
        
        dist = np.array([abs(r-new_r)] + [abs(w-new_w)] + [abs(T_H-new_T_H)]).max()
        dist_vec[iteration] = dist
        if iteration > 10:
            if dist_vec[iteration] - dist_vec[iteration-1] > 0:
                nu /= 2.0
                print 'New value of nu:', nu
        iteration += 1
        print "Iteration: %02d" % iteration, " Distance: ", dist

    eul_errors = np.ones(J)
    b_mat = np.zeros((S, J))
    n_mat = np.zeros((S, J))
    for j in xrange(J):
        solutions1 = opt.fsolve(Euler_equation_solver, np.append(bssmat[:, j], nssmat[:, j])* .9, args=(r, w, T_H, factor, j, params, chi_b, chi_n, theta, tau_bq, rho, lambdas, weights), xtol=1e-13)
        eul_errors[j] = np.array(Euler_equation_solver(solutions1, r, w, T_H, factor, j, params, chi_b, chi_n, theta, tau_bq, rho, lambdas, weights)).max()
        b_mat[:, j] = solutions1[:S]
        n_mat[:, j] = solutions1[S:]
    print 'SS fsolve euler error:', eul_errors.max()
    solutions = np.append(b_mat.flatten(), n_mat.flatten())
    other_vars = np.array([w, r, factor, T_H])
    solutions = np.append(solutions, other_vars)
    return solutions


def function_to_minimize(chi_params_init, params, weights_SS, rho_vec, lambdas, theta, tau_bq, e):
    '''
    Parameters:
        chi_params_init = guesses for chi_b

    Returns:
        The max absolute deviation between the actual and simulated
            wealth moments
    '''
    J, S, T, beta, sigma, alpha, Z, delta, ltilde, nu, g_y, tau_payroll, retire, mean_income_data, a_tax_income, b_tax_income, c_tax_income, d_tax_income, h_wealth, p_wealth, m_wealth, b_ellipse, upsilon = params
    print 'Print Chi_b: ', chi_params_init[:J]
    solutions_dict = pickle.load(open("OUTPUT/Saved_moments/minimization_solutions.pkl", "r"))
    solutions = solutions_dict['solutions']

    b_guess = solutions[:S*J]
    n_guess = solutions[S*J:2*S*J]
    wguess, rguess, factorguess, T_Hguess = solutions[2*S*J:]
    solutions = new_SS_Solver(b_guess.reshape(S, J), n_guess.reshape(S, J), wguess, rguess, T_Hguess, factorguess, chi_params_init[J:], chi_params_init[:J], params, iterative_params, theta, tau_bq, rho, lambdas, weights_SS)

    b_new = solutions[:S*J]
    n_new = solutions[S*J:2*S*J]
    w_new, r_new, factor_new, T_H_new = solutions[2*S*J:]
    # Wealth Calibration Euler
    error5 = list(misc_funcs.check_wealth_calibration(b_new.reshape(S, J)[:-1, :], factor_new, params))
    # labor calibration euler
    lab_data_dict = pickle.load(open("OUTPUT/Saved_moments/labor_data_moments.pkl", "r"))
    labor_sim = (n_new.reshape(S, J)*lambdas.reshape(1, J)).sum(axis=1)
    error6 = list(misc_funcs.perc_dif_func(labor_sim, lab_data_dict['labor_dist_data']))
    # combine eulers
    output = np.array(error5 + error6)
    # Constraints
    eul_error = np.ones(J)
    for j in xrange(J):
        eul_error[j] = np.abs(Euler_equation_solver(np.append(b_new.reshape(S, J)[:, j], n_new.reshape(S, J)[:, j]), r_new, w_new, T_H_new, factor_new, j, params, chi_params_init[:J], chi_params_init[J:], theta, tau_bq, rho, lambdas, weights_SS)).max()
    fsolve_no_converg = eul_error.max()
    if np.isnan(fsolve_no_converg):
        fsolve_no_converg = 1e6
    if fsolve_no_converg > 1e-4:
        output += 1e9
    else:
        var_names = ['solutions']
        dictionary = {}
        for key in var_names:
            dictionary[key] = locals()[key]
        pickle.dump(dictionary, open("OUTPUT/Saved_moments/minimization_solutions.pkl", "w"))
    if (chi_params_init <= 0.0).any():
        output += 1e9
    weighting_mat = np.eye(2*J + S)
    scaling_val = 100.0
    value = np.dot(scaling_val * np.dot(output.reshape(1, 2*J+S), weighting_mat), scaling_val * output.reshape(2*J+S, 1))
    print 'Value of criterion function: ', value.sum()
    return value.sum()

'''
------------------------------------------------------------------------
    Run SS in various ways, depending on the stage of the simulation
------------------------------------------------------------------------
'''

if SS_stage == 'constrained_minimization':
    # Generate initial guesses for chi^b_j and chi^n_s
    chi_params[0:J] = np.array([2, 10, 90, 350, 1700, 22000, 120000])
    chi_params[:J] = np.ones(J)
    chi_n_guess = np.array([47.12000874 , 22.22762421 , 14.34842241 , 10.67954008 ,  8.41097278
                             ,  7.15059004 ,  6.46771332 ,  5.85495452 ,  5.46242013 ,  5.00364263
                             ,  4.57322063 ,  4.53371545 ,  4.29828515 ,  4.10144524 ,  3.8617942  ,  3.57282
                             ,  3.47473172 ,  3.31111347 ,  3.04137299 ,  2.92616951 ,  2.58517969
                             ,  2.48761429 ,  2.21744847 ,  1.9577682  ,  1.66931057 ,  1.6878927
                             ,  1.63107201 ,  1.63390543 ,  1.5901486  ,  1.58143606 ,  1.58005578
                             ,  1.59073213 ,  1.60190899 ,  1.60001831 ,  1.67763741 ,  1.70451784
                             ,  1.85430468 ,  1.97291208 ,  1.97017228 ,  2.25518398 ,  2.43969757
                             ,  3.21870602 ,  4.18334822 ,  4.97772026 ,  6.37663164 ,  8.65075992
                             ,  9.46944758 , 10.51634777 , 12.13353793 , 11.89186997 , 12.07083882
                             , 13.2992811  , 14.07987878 , 14.19951571 , 14.97943562 , 16.05601334
                             , 16.42979341 , 16.91576867 , 17.62775142 , 18.4885405  , 19.10609921
                             , 20.03988031 , 20.86564363 , 21.73645892 , 22.6208256  , 23.37786072
                             , 24.38166073 , 25.22395387 , 26.21419653 , 27.05246704 , 27.86896121
                             , 28.90029708 , 29.83586775 , 30.87563699 , 31.91207845 , 33.07449767
                             , 34.27919965 , 35.57195873 , 36.95045988 , 38.62308152])
    chi_params[J:] = chi_n_guess
    chi_params = list(chi_params)
    # First run SS simulation with guesses at initial values for b, n, w, r, etc
    b_guess = np.ones((S, J)).flatten() * .01
    n_guess = np.ones((S, J)).flatten() * .5 * ltilde
    wguess = 1.2
    rguess = .06
    T_Hguess = 0
    factorguess = 100000
    solutions = new_SS_Solver(b_guess.reshape(S, J), n_guess.reshape(S, J), wguess, rguess, T_Hguess, factorguess, chi_params[J:], chi_params[:J], parameters, iterative_params, theta, tau_bq, rho, lambdas, omega_SS)
    variables = ['solutions', 'chi_params']
    dictionary = {}
    for key in variables:
        dictionary[key] = globals()[key]
    pickle.dump(dictionary, open("OUTPUT/Saved_moments/minimization_solutions.pkl", "w"))

    function_to_minimize_X = lambda x: function_to_minimize(x, parameters, omega_SS, rho, lambdas, theta, tau_bq, e)
    bnds = tuple([(1e-6, None)] * (S + J))
    chi_params = opt.minimize(function_to_minimize_X, chi_params, method='TNC', tol=1e-14, bounds=bnds).x
    print 'The final bequest parameter values:', chi_params

    solutions_dict = pickle.load(open("OUTPUT/Saved_moments/minimization_solutions.pkl", "r"))
    b_guess = solutions_dict['solutions'][:S*J]
    n_guess = solutions_dict['solutions'][S*J:2*S*J]
    wguess, rguess, factorguess, T_Hguess = solutions[2*S*J:]

    solutions = new_SS_Solver(b_guess.reshape(S, J), n_guess.reshape(S, J), wguess, rguess, T_Hguess, factorguess, chi_params[J:], chi_params[:J], parameters, iterative_params, theta, tau_bq, rho, lambdas, omega_SS)
elif SS_stage == 'SS_init':
    variables = pickle.load(open("OUTPUT/Saved_moments/minimization_solutions.pkl", "r"))
    for key in variables:
        globals()[key] = variables[key]
    b_guess = solutions[:S*J]
    n_guess = solutions[S*J:2*S*J]
    wguess, rguess, factorguess, T_Hguess = solutions[2*S*J:]
    solutions = new_SS_Solver(b_guess.reshape(S, J), n_guess.reshape(S, J), wguess, rguess, T_Hguess, factorguess, chi_params[J:], chi_params[:J], parameters, iterative_params, theta, tau_bq, rho, lambdas, omega_SS)
elif SS_stage == 'SS_tax':
    variables = pickle.load(open("OUTPUT/Saved_moments/SS_init_solutions.pkl", "r"))
    for key in variables:
        globals()[key] = variables[key]
    b_guess = solutions[:S*J]
    n_guess = solutions[S*J:2*S*J]
    wguess, rguess, factorguess, T_Hguess = solutions[2*S*J:]
    solutions = new_SS_Solver(b_guess.reshape(S, J), n_guess.reshape(S, J), wguess, rguess, T_Hguess, factorguess, chi_params[J:], chi_params[:J], parameters, iterative_params, theta, tau_bq, rho, lambdas, omega_SS)


'''
------------------------------------------------------------------------
    Save the initial values in various ways, depending on the stage of
        the simulation
------------------------------------------------------------------------
'''

if SS_stage == 'constrained_minimization':
    var_names = ['solutions', 'chi_params']
    dictionary = {}
    for key in var_names:
        dictionary[key] = globals()[key]
    pickle.dump(dictionary, open("OUTPUT/Saved_moments/minimization_solutions.pkl", "w"))
elif SS_stage == 'SS_init':
    var_names = ['solutions', 'chi_params']
    dictionary = {}
    for key in var_names:
        dictionary[key] = globals()[key]
    pickle.dump(dictionary, open("OUTPUT/Saved_moments/SS_init_solutions.pkl", "w"))
elif SS_stage == 'SS_tax':
    var_names = ['solutions', 'chi_params']
    dictionary = {}
    for key in var_names:
        dictionary[key] = globals()[key]
    pickle.dump(dictionary, open("OUTPUT/Saved_moments/SS_tax_solutions.pkl", "w"))


bssmat = solutions[0:(S-1) * J].reshape(S-1, J)
bq = solutions[(S-1)*J:S*J]
bssmat_s = np.array(list(np.zeros(J).reshape(1, J)) + list(bssmat))
bssmat_splus1 = np.array(list(bssmat) + list(bq.reshape(1, J)))
nssmat = solutions[S * J:2*S*J].reshape(S, J)
wss, rss, factor_ss, T_Hss = solutions[2*S*J:]

Kss = house.get_K(bssmat_splus1, omega_SS)
Lss = firm.get_L(e, nssmat, omega_SS)
Yss = firm.get_Y(Kss, Lss, parameters)

BQss = (1+rss)*(np.array(list(bssmat) + list(bq.reshape(1, J))).reshape(
    S, J) * omega_SS * rho.reshape(S, 1)).sum(0)
b_s = np.array(list(np.zeros(J).reshape((1, J))) + list(bssmat))
taxss = tax.total_taxes(rss, b_s, wss, e, nssmat, BQss, lambdas, factor_ss, T_Hss, None, 'SS', False, parameters, theta, tau_bq)
cssmat = house.get_cons(rss, b_s, wss, e, nssmat, BQss.reshape(1, J), lambdas.reshape(1, J), bssmat_splus1, parameters, taxss)

house.constraint_checker_SS(bssmat, nssmat, cssmat, parameters)

'''
------------------------------------------------------------------------
Generate variables for graphs
------------------------------------------------------------------------
b_s        = SxJ array of bssmat in period t
b_splus1        = SxJ array of bssmat in period t+1
b_splus2        = SxJ array of bssmat in period t+2
euler_savings      = euler errors from savings euler equation
euler_labor_leisure      = euler errors from labor leisure euler equation
------------------------------------------------------------------------
'''
b_s = np.array(list(np.zeros(J).reshape((1, J))) + list(bssmat))
b_splus1 = bssmat_splus1
b_splus2 = np.array(list(bssmat_splus1[1:]) + list(np.zeros(J).reshape((1, J))))

chi_b = np.tile(chi_params[:J].reshape(1, J), (S, 1))
chi_n = np.array(chi_params[J:])
euler_savings = np.zeros((S, J))
euler_labor_leisure = np.zeros((S, J))
for j in xrange(J):
    euler_savings[:, j] = house.euler_savings_func(wss, rss, e[:, j], nssmat[:, j], b_s[:, j], b_splus1[:, j], b_splus2[:, j], BQss[j], factor_ss, T_Hss, chi_b[:, j], parameters, theta[j], tau_bq[j], rho, lambdas[j])
    euler_labor_leisure[:, j] = house.euler_labor_leisure_func(wss, rss, e[:, j], nssmat[:, j], b_s[:, j], b_splus1[:, j], BQss[j], factor_ss, T_Hss, chi_n, parameters, theta[j], tau_bq[j], lambdas[j])
'''
------------------------------------------------------------------------
    Save the values in various ways, depending on the stage of
        the simulation, to be used in TPI or graphing functions
------------------------------------------------------------------------
'''
if SS_stage == 'constrained_minimization':
    var_names = ['retire', 'nssmat', 'wss', 'factor_ss', 'e',
                 'J', 'omega_SS']
    dictionary = {}
    for key in var_names:
        dictionary[key] = globals()[key]
    pickle.dump(dictionary, open("OUTPUT/Saved_moments/payroll_inputs.pkl", "w"))
if SS_stage == 'SS_init' or SS_stage == 'SS_tax':
    # Pickle variables
    var_names = ['Kss', 'bssmat', 'Lss', 'nssmat', 'Yss', 'wss', 'rss',
                 'BQss', 'factor_ss', 'bssmat_s', 'cssmat', 'bssmat_splus1',
                 'T_Hss', 'euler_savings', 'euler_labor_leisure', 'chi_n', 'chi_b']
    dictionary1 = {}
    for key in var_names:
        dictionary1[key] = globals()[key]
    if SS_stage == 'SS_init':
        pickle.dump(dictionary1, open("OUTPUT/SSinit/ss_init_vars.pkl", "w"))
        bssmat_init = bssmat_splus1
        nssmat_init = nssmat
        # Pickle variables for TPI initial values
        var_names = ['bssmat_init', 'nssmat_init']
        dictionary2 = {}
        for key in var_names:
            dictionary2[key] = globals()[key]
        pickle.dump(dictionary2, open("OUTPUT/SSinit/ss_init_tpi_vars.pkl", "w"))
    elif SS_stage == 'SS_tax':
        pickle.dump(dictionary1, open("OUTPUT/SS/ss_vars.pkl", "w"))
