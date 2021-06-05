#!/usr/bin/env python
'''
Analysis of Tinker BAR data using pymbar

> t_bar.py sample.bar
'''

import numpy as np
import pandas as pd
import pymbar
import sys
import os

def convert_1d(arr):
  '''
  convert nx2 array to nx1 array of the difference
  '''
  if len(arr.shape) == 1:
    arr1 = arr
  elif len(arr.shape) ==2 and arr.shape[1] == 2:
    arr1 = arr[:, 0] - arr[:, 1]
  else:
    arr1 = arr[:, 0]
  return arr1
  
def calc_eff_size(arr, equil=False):
  '''
  return t0, g
  '''
  arr1 = convert_1d(arr)
  NBLOCK = 71
  nskip = max(1, len(arr1)//NBLOCK)
  t0 = 0
  indices = np.arange(len(arr1), dtype=int)
  if equil:
    [t0, g, Neff_max] = pymbar.timeseries.detectEquilibration(arr1, nskip=nskip)
    #indices = pymbar.timeseries.subsampleCorrelatedData(arr1[t0:], g=g)
  else:
    indices = pymbar.timeseries.subsampleCorrelatedData(arr1)
    g = len(arr1)/len(indices)
  return t0, g

def resample(arr, n):
  if n == len(arr):
    return arr
  else:
    return arr[np.random.randint(0, len(arr), n, dtype=int)]
    
def subsample2(arr1, arr2, equil=False, corr=True, skip1=0, skip2=0, nmin=100):
  '''
  resample arrays based on their effective sample size
  the output arrays are proportional (but not equal) to the number of effetive samples

  return:
    arr1b: resampled arr1
    arr2b
    t1: starting frame number for arr1
    t2
    g1: effective sample size for arr1
    g2
    teff: effective sample size for resampled arrays
  '''
  kwargs = {'equil':equil}
  g1 = 1
  g2 = 1
  if equil:
    t1, g1 = calc_eff_size(arr1, **kwargs)
    t2, g2 = calc_eff_size(arr2, **kwargs)
    if not corr:
      g1 = 1
      g2 = 1
  else:
    t1 = skip1
    t2 = skip2
    if corr:
      _t1, g1 = calc_eff_size(arr1[skip1:], **kwargs)
      _t2, g2 = calc_eff_size(arr2[skip2:], **kwargs)
  teff = min(g1, g2)
  n1 = len(arr1) - t1
  n2 = len(arr2) - t2
  if corr:
    if g1 < g2:
      n1 = int(g2/g1*n1)
    elif g2 < g1:
      n2 = int(g1/g2*n2)
  _min = min(n1, n2)
  if _min < nmin:
    n1 = n1 * nmin//_min
    n2 = n2 * nmin//_min
    print("Augmenting data %d > %d"%(_min, nmin))
  arr1b = resample(arr1[t1:], n1)
  arr2b = resample(arr2[t2:], n2)
  teff = n1/(len(arr1)-t1)*g1
  return arr1b, arr2b, t1, g1, t2, g2, teff

def subsample(arr, equil=False, corr=True):
  arr1 = convert_1d(arr)
  NBLOCK = 71
  nskip = max(1, len(arr1)//NBLOCK)
  t0 = 0
  indices = np.arange(len(arr1), dtype=int)
  if equil and corr:
    [t0, g, Neff_max] = pymbar.timeseries.detectEquilibration(arr1, nskip=nskip)
    indices = pymbar.timeseries.subsampleCorrelatedData(arr1[t0:], g=g)
  elif corr:
    indices = pymbar.timeseries.subsampleCorrelatedData(arr1)
  return [_+t0 for _ in indices]

def get_index_summary(indices):
  return '(%d,%d,%d)'%(indices[0], indices[-1], indices[1]-indices[0])

def get_index_summary2(idx1, idx2):
  msg = 'A:%s B:%s'%(get_index_summary(idx1), get_index_summary(idx2))
  return msg

def read_tinker_bar(inp, temp=298, press=1.0):
  beta = 1.0/(8.314*temp/4184)
  # bar * ang^3 in kcal/mol
  PV_UNIT_CONV = 1e5*1e-30/4184*6.02e23
  with open(inp, 'r') as fh:
    lines = fh.readlines()
    if len(lines) == 0:
      return
    w = lines[0].split()
    if len(w) == 0 or (not w[0].isdigit()):
      return
    n1 = int(w[0])

    w = lines[n1+1].split()
    if len(w) == 0 or (not w[0].isdigit()):
      return
    n2 = int(w[0])

    if len(lines) != n1+n2+2:
      print("nlines (%d) != %d + %d"%(len(lines), n1, n2))
      return

    arr1 = np.fromstring(''.join(lines[1:n1+1]), sep=' ').reshape(-1, 4)
    arr2 = np.fromstring(''.join(lines[n1+2:]), sep=' ').reshape(-1, 4)

    u1 = beta*(arr1[:, 1:3] + press*arr1[:, 3:4]*PV_UNIT_CONV)
    u2 = beta*(arr2[:, 1:3] + press*arr2[:, 3:4]*PV_UNIT_CONV)
    #return (np.concatenate((u1[idx1], u2[idx2]), axis=0).transpose(), [len(idx1), len(idx2)], msg)
    return u1, u2

def concat_arr(arr1, arr2, idx1, idx2):
  msg = get_index_summary2(idx1, idx2)
  return (np.concatenate((arr1[idx1], arr2[idx2]), axis=0).transpose(), [len(idx1), len(idx2)], msg)

def tinker_to_mbar(arr1, arr2, equil=False, corr=True):
  assert len(arr1.shape) == 2 and arr1.shape[1] == 2
  idx1 = subsample(arr1[:, 1] - arr1[:, 0], equil=equil, corr=corr)
  idx2 = subsample(arr2[:, 1] - arr2[:, 0], equil=equil, corr=corr)
  return concat_arr(arr1, arr2, idx1, idx2)

def arr_to_mbar(arr1, arr2):
  return (np.concatenate((arr1, arr2), axis=0).transpose(), [len(arr1), len(arr2)])

def exp_ave(ener, return_sd=True):
  emax = np.max(ener)
  if return_sd:
    _sd = np.std(ener)
    return -np.log(np.mean(np.exp(-(ener-emax)))) + emax, _sd
  return -np.log(np.mean(np.exp(-(ener-emax)))) + emax

def calc_mbar(u_kn, N_k, teff=1):
  #data = concat_arr(arr1, arr2, idx1, idx2)
  cols = 'start_A end_A start_B end_B g_A g_B dF(kcal/mol) sd_dF(kcal/mol) dF_fwd dF_bwd dE_fwd dE_bwd sd_fwd sd_bwd p_A(traj_B) p_B(traj_A) overlapEig'.split()
  if u_kn is None:
    return cols

  mbar = pymbar.MBAR(u_kn, N_k)
  results = mbar.getFreeEnergyDifferences()
  overlap = mbar.computeOverlap()
  #msg1 = get_index_summary(idx1)
  #msg2 = get_index_summary(idx2)
  es_fwd = (u_kn[1, 0:N_k[0]] - u_kn[0, 0:N_k[0]])
  es_bwd = (u_kn[0, N_k[0]:sum(N_k[0:2])] - u_kn[1, N_k[0]:sum(N_k[0:2])])
  de_fwd = np.mean(es_fwd)
  de_bwd = np.mean(es_bwd)

  fwd, sd_fwd = exp_ave(es_fwd)
  bwd, sd_bwd = exp_ave(es_bwd)
  return results[0][0, 1], results[1][0, 1]*np.sqrt(teff), fwd, -bwd, de_fwd, -de_bwd, sd_fwd, sd_bwd, overlap['matrix'][0, 1], overlap['matrix'][1, 0], overlap['scalar']

def calc_dg():

  NBLOCK = 5
  NMIN = 100
  opts = [{'equil':False, 'corr':False}, 
          {'equil':False, 'corr':True},
          {'equil':True,  'corr':True},
          ]
  names = ['Free energy (all) ',
           'Free energy (decorrelated) ',  
           'Free energy (equilibrated) ',  
           ]
  names = 'all uncorr equ'.split()

  #df_out = pd.DataFrame(columns='traj_A traj_B dF(kcal/mol) sd_dF(kcal/mol) overlapAB overlapBA eig'.split())
  df_out = pd.DataFrame(columns=calc_mbar(None, None))
  data0 = read_tinker_bar(sys.argv[1])
  if data0 is None:
    return
  for opt, name in zip(opts, names):
    #data = tinker_to_mbar(data0[0], data0[1], **opt)
    #idx1 = subsample(data0[0], **opt)
    #idx2 = subsample(data0[1], **opt)
    #print('%-60s : %.4f +- %.4f kcal/mol'%((name + data[2]), results[0][0,1], results[1][0,1]))
    #df_out.loc[name, :] = 'A', 'B', results[0][0,1], results[1][0,1], overlap['matrix'][0, 1], overlap['matrix'][1, 0], overlap['scalar']
    arr1, arr2, t1, g1, t2, g2, teff = subsample2(data0[0], data0[1], **opt)
    u_kn, N_k = arr_to_mbar(arr1, arr2)
    res = calc_mbar(u_kn, N_k, teff)
    i1x, i1y, i2x, i2y = t1, len(data0[0]), t2, len(data0[1])
    df_out.loc[name, :] = [i1x, i1y, i2x, i2y, g1, g2] + list(res)

  if min(len(data0[0]) , len(data0[1])) >= NBLOCK*NMIN:
    for opt, name1 in zip(opts, names):
      bn1 = len(data0[0])//NBLOCK
      bn2 = len(data0[1])//NBLOCK
      for i in range(NBLOCK):
        #opt = {'equil':False, 'corr':False}
        i1x, i1y, i2x, i2y = bn1*i, bn1*(i+1), bn2*i, bn2*(i+1)
        arr1, arr2, t1, g1, t2, g2, teff = subsample2(data0[0][bn1*i:bn1*(i+1)], data0[1][bn2*i:bn2*(i+1)], **opt)
        u_kn, N_k = arr_to_mbar(arr1, arr2)
        res = calc_mbar(u_kn, N_k, teff)

        name = "block%d%s"%(i+1, name1)
        df_out.loc[name, :] = [i1x, i1y, i2x, i2y, g1, g2] + list(res)
  print(df_out.to_string(max_rows=len(df_out.index), max_cols=len(df_out.columns)))

calc_dg()
  

