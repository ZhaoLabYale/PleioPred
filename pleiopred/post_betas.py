try: 
    import scipy as sp
except Exception:
    print 'Using Numpy instead of Scipy.'
    import numpy as sp
    
from scipy import linalg 
import pdb
import plinkio
from plinkio import plinkfile
import random
import numpy as np
import time
import gzip
import itertools as it
from sklearn import metrics

import getopt
import sys
import traceback
import time
import os
import gzip
import itertools as it
import scipy as sp
import h5py
from scipy import stats

def bi_mcmc_all_chr(beta_hats1, beta_hats2, Pi, pr_sig1, pr_sig2, zj_p, start_betas1=None, start_betas2=None, n1=1000, n2=1000, ld_radius=100, ld_dict1=None, ld_dict2=None, h2_D1=None, h2_D2=None):
    """
    MCMC of non-infinitesimal model
    """
    #Pi = sp.random.dirichlet((alpha,alpha,alpha,alpha),1).flatten()
    m = len(beta_hats1)
    
    curr_betas1 = sp.copy(start_betas1)
    curr_post_means1 = sp.zeros(m)
#    avg_betas1 = sp.zeros(m)

    curr_betas2 = sp.copy(start_betas2)
    curr_post_means2 = sp.zeros(m)
#    avg_betas2 = sp.zeros(m)

#    Pi_traj = sp.zeros((4,num_iter+1))
#    Pi_traj[:,0] = Pi
#    s_traj1 = sp.zeros((m,num_iter+1))
#    s_traj2 = sp.zeros((m,num_iter+1))
#    s_traj1[:,0] = start_betas1
#    s_traj2[:,0] = start_betas2
#    m_traj1 = sp.zeros((m,num_iter))
#    m_traj2 = sp.zeros((m,num_iter))

    # Iterating over effect estimates in sequential order
    h2_est1 = max(0.00001,sp.sum(curr_betas1 ** 2))
    h2_est2 = max(0.00001,sp.sum(curr_betas2 ** 2))
    shrink_factor = min(1-zj_p, h2_D1/h2_est1, h2_D2/h2_est2)

    rand_ps = sp.random.random(m)
    iter_order = sp.arange(m)
    for i, snp_i in enumerate(iter_order):
        if pr_sig1[snp_i]==0 or pr_sig2[snp_i]==0:
            if pr_sig1[snp_i]==0:
                curr_post_means1[snp_i] = 0
                curr_betas1[snp_i] = 0
            if pr_sig2[snp_i]==0:
                curr_post_means2[snp_i] = 0
                curr_betas2[snp_i] = 0
        else:
            start_i = max(0, snp_i - ld_radius)
            focal_i = min(ld_radius, snp_i)
            stop_i = min(m, snp_i + ld_radius + 1)
            D1_i = ld_dict1[snp_i]
            D2_i = ld_dict2[snp_i]
            local_betas1 = curr_betas1[start_i: stop_i]
            local_betas2 = curr_betas2[start_i: stop_i]
            local_betas1[focal_i] = 0
            local_betas2[focal_i] = 0
            num1 = beta_hats1[snp_i] - sp.dot(D1_i , local_betas1)
            num2 = beta_hats2[snp_i] - sp.dot(D2_i , local_betas2)

            v1 = pr_sig1[snp_i]/(Pi[0]+Pi[1])
            v2 = pr_sig2[snp_i]/(Pi[0]+Pi[2])

            C1 = 1.0/(n1+1.0/v1) ##post var1
            C2 = 1.0/(n2+1.0/v2) ##post var2
            mu1 = n1*num1*C1
            mu2 = n2*num2*C2
            NC1 = C1*n1**2
            NC2 = C2*n2**2
            CR1 = 1.0/(n1*v1+1.0)
            CR2 = 1.0/(n2*v2+1.0)

            w11 = Pi[0]*np.exp((np.log(CR1) + np.log(CR2))/2.0 + NC2*num2**2/2.0 + NC1*num1**2/2.0)
            w10 = Pi[1]*np.exp(np.log(CR1)/2.0 + NC1*num1**2/2.0)
            w01 = Pi[2]*np.exp(np.log(CR2)/2.0 + NC2*num2**2/2.0)
            w00 = Pi[3]
            wsum = w11 + w10 + w01 + w00
#            postP = [w11/wsum,(w11+w10)/wsum,(w11+w10+w01)/wsum]
#            outP = sp.array([w11,w10,w01,w00])/wsum
            postP = sp.array([w11, w11+w10, w11+w10+w01])*shrink_factor/wsum
            curr_post_means1[snp_i] = mu1*(w11+w10)/wsum
            curr_post_means2[snp_i] = mu2*(w11+w01)/wsum

            if rand_ps[i]<=postP[0]:
                proposed_beta1 = stats.norm.rvs(mu1, C1, size=1)
                proposed_beta2 = stats.norm.rvs(mu2, C2, size=1)
            if rand_ps[i]>postP[0] and rand_ps[i]<=postP[1]:
                proposed_beta1 = stats.norm.rvs(mu1, C1, size=1)
                proposed_beta2 = 0
            if rand_ps[i]>postP[1] and rand_ps[i]<=postP[2]:
                proposed_beta1 = 0
                proposed_beta2 = stats.norm.rvs(mu2, C2, size=1)
            if rand_ps[i]>postP[2]:
                proposed_beta1 = 0
                proposed_beta2 = 0

            curr_betas1[snp_i] = proposed_beta1
            curr_betas2[snp_i] = proposed_beta2

#            s_traj1[snp_i,k+1] = proposed_beta1
#            s_traj2[snp_i,k+1] = proposed_beta2
#
#            m_traj1[snp_i,k] = curr_post_means1[snp_i]
#            m_traj2[snp_i,k] = curr_post_means2[snp_i]

    ########### update Pi ##########
    A1 = sp.sum((curr_betas1!=0) & (curr_betas2!=0))
    A2 = sp.sum((curr_betas1!=0) & (curr_betas2==0))
    A3 = sp.sum((curr_betas1==0) & (curr_betas2!=0))
    A4 = sp.sum((curr_betas1==0.0) & (curr_betas2==0.0))
#    Pi = sp.random.dirichlet((alpha+A1,alpha+A2,alpha+A3,alpha+A4),1).flatten()
#    if k >= burn_in:
#        avg_betas1 += curr_post_means1 #Averaging over the posterior means instead of samples.
#        avg_betas2 += curr_post_means2
    return {'proposed_betas1':curr_betas1, 'proposed_betas2':curr_betas2, 'curr_post_means1':curr_post_means1, 'curr_post_means2':curr_post_means2, 'A1':A1, 'A2':A2, 'A3':A3, 'A4':A4}

