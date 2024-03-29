import numpy as np
import emcee
from scipy.optimize import minimize
import numdifftools  as nd
from collections.abc import Iterable
from multiprocessing import Pool, cpu_count

def run_minimize(func, pos0, dpos=None, method='Powell', tol=None,
                 callback=None, options=None, verbose=False):
    """ Function to find maximum-likelihood parameters

    Parameters
    ----------
    func: function
        Likelihood function to maximize. Must be of the form f(x,*args)
    pos: list(float)
        A best guess of the parameter values to initiate the sampler.
    dpos: list(float)
        Irrelevant (optional)
    method: string
        Minimizer method, only 'Powell' tested so far (optional,
        default='Powell')
    callback : callable
        Called after each iteration of the minimizer, as callback(xk), where xk
        is the current parameter vector (optional, default=None)
    tol : float
        Tolerance for termination. For detailed control, use solver-specific
        options.
    options : dict
        Optional dictionary containing additional options for each method.
        One particularly
        useful option is maxiter:int

    Returns
    -------
        Dictionary with maximum likelihood parameters and status of minimizer
        on exit.
    """
    if verbose:
        print("Minimizing")
    def mfunc(params, *args):
        return -func(params, *args)
    res = minimize(mfunc, pos0, method=method, tol=tol, callback=callback,
                   options=options)
    if not isinstance(res.x, Iterable):
        x = [res.x]
    else:
        x = res.x
    return {'params_ML':x, 'ML_success':res.success, 'ML_nev':res.nfev}

def run_fisher(func,pos0,dpos=None,ml_first=False,ml_method='Powell',ml_options=None,verbose=False):
    """ Function to find Fisher matrix uncertainties (optionally) maximum-likelihood parameters

    Parameters
    ----------
    func: function
        Likelihood function to maximize. Must be of the form f(x,*args)
    pos: list(float)
        Central value to use when computing the Fisher matrix (see ml_first below).
    dpos: list(float)
        Irrelevant (optional)
    ml_first: bool
        If True, the maximum-likelihood will be found and used as central value when computing the
        Fisher matrix.
    ml_method: string
        Minimizer method, only 'Powell' tested so far (optional, default='Powell')
    ml_options : dict
        Optional dictionary containing additional options for the minimizer. One particularly
        useful option is maxiter:int

    Returns
    -------
        Dictionary with central parameter values, Fisher matrix and Fisher bias vector
    """
    def mfunc(p,*a) :
        return -func(p,*a)
    
    if ml_first :
        if verbose :
            print("Finding ML")
        res=minimize(mfunc,pos0,method=ml_method,options=ml_options)
        pcent=res.x
        ml_success=res.success
    else :
        pcent=pos0
        ml_success=None
    if verbose :
        print("Computing gradient")
    fisher_v=-nd.Gradient(mfunc)(pcent)
    if verbose :
        print("Computing Hessian")
    fisher_m=nd.Hessian(mfunc)(pcent)
    
    return {'params_cent':pcent,'fisher_m':fisher_m,'fisher_v':fisher_v,'ML_success':ml_success}

def run_emcee(func, pos0, dpos=None, nwalkers=200, nsamps=200,
              nburn=50, verbose=False, conv_F=50, conv_perc=0.01, **kwargs):
    """ Function to run the emcee sampler on a given likelihood function.

    Parameters
    ----------
    func: function
        Likelihood function to sample, this must obey the requirements of the
        `emcee` module.
    pos: list(float)
        A best guess of the parameter values to initiate the sampler.
    dpos: list(float)
        A best guess of the parameter uncertainties to guide the initial steps
        (optional,default=None).
    nwalkers: int
        Number of independent walkers to start (optional, default=100).
    nsamps: int
        Number of samples to be taken by each walker (optional, default=500).
    nbrun: int
        Number of samples to be taken as burn-in, and discarded before returning
        the chain.

    Returns
    -------
        Dictionary containing the parameter chains.
    """
    if verbose:
        print("Sampling")
    ndim = len(pos0)

    #Set up initial displacement amplitudes
    if dpos is None:
        dpos = 1e-2*np.ones(ndim)
    dp = np.zeros(ndim)
    for i, d in enumerate(dpos) :
        if ((d is None) or (d <= 0)) :
            dp[i] = 1e-2
        else:
            dp[i] = d * 0.1
    # initial positions of the walkers
    pos = [pos0 + dp * np.random.randn(ndim) for i in range(nwalkers)]
    # Do MCMC sampling, with early stopping if the convergence criterion is
    # met.

    sampler = emcee.EnsembleSampler(nwalkers, ndim, func, **kwargs)
    # This will be useful to testing convergence
    old_tau = np.inf
    # Now we'll sample for up to nsamps steps
    autocorr = []
    for _ in sampler.sample(pos, iterations=nsamps):
        # Only check convergence every 100 steps
        if sampler.iteration % 100:
            continue
        # Compute the autocorrelation time so far
        # Using tol=0 means that we'll always get an estimate even
        # if it isn't trustworthy
        tau = sampler.get_autocorr_time(tol=0)
        autocorr.append((sampler.iteration, np.mean(tau)))
        print(autocorr[-1])
        # Check convergence
        converged = np.all(tau * conv_F < sampler.iteration)
        converged &= np.all(np.abs(old_tau - tau) / tau < conv_perc)
        if converged:
            break
        old_tau = tau
    autocorr = np.array(autocorr)
    samples = sampler.chain[:, nburn:, :].reshape((-1, ndim))
    return {'chains':samples, 'autocorr':autocorr}

def clean_pixels(maplike,sampler,d_params=None,**sampler_args):
    """ Function to combine a given MapLike likelihood object and a given
    sampler.

    Parameters
    ----------
    maplike: MapLike
        Instance of the Maplike method.
    sampler: function
        Which sampling function to be used.
    d_params: (list(float))
        Expected width for each parameter (pass None if no idea).
    sampler_args: dict
        Keyword arguments containing hyperparameters specific to whichever
        sampler was chosen.

    Returns
    -------
    list(array_like(float))
        List of MCMC chains corresponding to the pixels in `ipix`.
    """
    outputs=sampler(maplike.marginal_spectral_likelihood,
                    pos0=maplike.var_prior_mean,
                    dpos=d_params,
                    **sampler_args)
    return outputs
