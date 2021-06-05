#!/usr/bin/env python
import numpy as np
import pandas as pd
import sys
from scipy.interpolate import UnivariateSpline, PchipInterpolator
import scipy.optimize as optimize
import scipy.integrate as integrate
from scipy import interpolate
import bisect

def compute_err_std(df1):
  columns = 'sd_all sd_equ sd_dec diff_f sd_e over2'.split()
  columns += ['err_'+_ for _ in 'sd_all sd_equ sd_dec diff_f sd_e over2'.split()]
  if df1 is None:
    return columns
  res1 = []
  res2 = []
  arrs = []
  arrs.append(df1['sd_dF(kcal/mol)'].iloc[3:8].to_numpy())
  arrs.append(df1['sd_dF(kcal/mol)'].iloc[13:18].to_numpy())
  arrs.append(df1['sd_dF(kcal/mol)'].iloc[8:13].to_numpy())
  arrs.append((df1['dF_fwd']-df1['dF_bwd']).iloc[3:8].to_numpy())
  arrs.append(np.sqrt(df1['sd_fwd'].iloc[3:8]**2.0 + df1['sd_bwd'].iloc[3:8]**2.0).to_numpy())
  arrs.append(df1['overlapEig'].iloc[3:8].to_numpy())
  for arr in arrs:
    res1.append(np.mean(arr))
    #res2.append(np.std(arr))
    res2.append((arr[0]))
  return res1 + res2

def compute_convergence(df1):
  columns = 'dF sd_all sd_equ sd_dec diff_f diff_e sd_e over2 over1 over2b over1b'.split()
  if df1 is None:
    return columns
  dF = df1.loc['equ', 'dF(kcal/mol)']
  sd_all = df1.loc['all', 'sd_dF(kcal/mol)']
  sd_equ = df1.loc['equ', 'sd_dF(kcal/mol)']
  sd_dec = df1.loc['uncorr', 'sd_dF(kcal/mol)']
  diff_f = np.abs(df1.loc['equ', 'dF_fwd'] - df1.loc['equ', 'dF_bwd'])
  diff_e = np.abs(df1.loc['equ', 'dE_fwd'] - df1.loc['equ', 'dE_bwd'])
  sd_e = np.sqrt(df1.loc['all', 'sd_fwd']**2.0 + df1.loc['all', 'sd_bwd']**2.0)
  over2= df1.loc['all', 'overlapEig']
  over1 = min(df1.loc['all', 'p_B(traj_A)'], df1.loc['all', 'p_A(traj_B)'])
  over2b= df1.loc['equ', 'overlapEig']
  over1b = min(df1.loc['equ', 'p_B(traj_A)'], df1.loc['equ', 'p_A(traj_B)'])
  return dF, sd_all, sd_equ, sd_dec, diff_f, diff_e, sd_e, over2, over1, over2b, over1b

def est_err(arr1):
  err1 = sum(arr1**2.0)
  ts2 = arr1/np.mean(arr1)
  ts3 = ts2**2.0
  ts3 = ts3 / np.mean(ts3)
  #print(ts2)
  #print(ts3)
  err2 = sum(arr1**2.0/ts2)
  err3 = sum(arr1**2.0/ts3)
  em = np.mean(arr1)
  print(np.max(arr1)/em, np.min(arr1)/em)
  return err1, err2, err3

def seq_to_count(indices):
  '''
  Convert [9, 9, 8, 9, 9, 9] to [9, 8, 9], [2, 1, 3]
  '''
  n = 1
  nr = []
  count = []
  for i in range(1, len(indices)):
    if indices[i] != indices[i-1]:
      nr.append(indices[i-1])
      count.append(n)
      n = 1
    elif i+1 == len(indices):
      nr.append(indices[i-1])
      count.append(n+1)
    else:
      n += 1
  return nr, count

def split_lamb_array(lambs):
  assert len(lambs.shape) == 2
  rep = lambs[1:] == lambs[:-1]
  diff = lambs[1:] != lambs[:-1]
  nchange = np.sum(rep, axis=1)
  idx = []
  iprev = 0
  n = 0
  icurr = 0
  for i in range(lambs.shape[0]-1):
    if sum(diff[i]) > 0:
      icurr = np.arange(lambs.shape[1])[diff[i]][0]
    idx.append(icurr)
  ilamb, ns = seq_to_count(idx)
  return ilamb, ns
    
def find_lambs(sd_ener, func_e, l0, lmax, nlambs, return_n=False, target_n=None):
  lambs = [l0]
  n2 = 0
  for i in range(nlambs):
    #print(integrate.quad(func_dedl, lambs[-1], lmax))
    #func = lambda t: integrate.quad(func_dedl, lambs[-1], t)[0] - sd_ener
    func = lambda t: func_e(t)-func_e(lambs[-1]) - sd_ener
    if func(lmax) < 0:
      lambs.append(lmax)
      n2 = (func(lmax) - func(lambs[-1])) / sd_ener
      break
    _l = optimize.bisect(func, lambs[-1], lmax)
    lambs.append(_l)
    if i == nlambs - 1:
      n2 = (func(lmax) - func(_l)) / sd_ener
  #print('n corr', n2)
  n_total = len(lambs) + n2
  if return_n:
    if target_n is not None:
      return n_total - target_n
    return n_total
  return lambs , n_total

def adjust_lamb1(lambs, err1, n_new = None):
  if n_new is None:
    n_new = len(lambs)
  lambs1 = 0.5*(lambs[1:] + lambs[:-1])
  dls = (lambs[1:] - lambs[:-1])
  dedl = err1/dls
  #dedlf = UnivariateSpline(lambs1, dedl, k=1, s=0, ext=3)
  dedlf = interpolate.interp1d(lambs[:-1], dedl, kind='previous', fill_value='extrapolate')
  esum = [0, err1[0]]
  for e in err1[1:]:
    esum.append(esum[-1] + e)
  #esumf = interpolate.interp1d(lambs, esum, kind='linear', fill_value='extrapolate')
  esumf = PchipInterpolator(lambs, esum, extrapolate=True)

  xs0 = np.linspace(lambs[0], lambs[-1], 20)
  _sde = optimize.bisect(find_lambs, np.min(err1)/10, np.max(err1)*10, args=(esumf, lambs[0], lambs[-1], n_new, True, n_new))
  lambs_new, _n = find_lambs(_sde, esumf, lambs[0], lambs[-1], n_new)
  return lambs_new

def adjust_lambs(lambs, err1, n_new = None, redist=False):
  '''
  lambs: n*m, n is N of states, m is N of lambda variables
  err1: errors between two states
  n_new: new number of states
  redist: redistribute N of lambdas among different lambda variables
  '''
  assert len(lambs) == len(err1) + 1
  if n_new is None:
    n_new = len(lambs)
  ilamb, ns = split_lamb_array(lambs)
  arr2 = np.zeros((0, lambs.shape[1]))
  for i in range(len(ns)):
    i1 = sum(ns[:i])
    i2 = sum(ns[:i+1])
    arr1 = adjust_lamb1(lambs[i1:i2+1, ilamb[i]], err1[i1:i2])

    arr1b = np.zeros((len(arr1), lambs.shape[1]))
    arr1b[:, :] = lambs[i1:(i1+1), :]
    arr1b[:, ilamb[i]] = arr1
    if i > 0:
      arr1b = arr1b[1:]
    arr2 = np.concatenate([arr2, arr1b], axis=0)
  return arr2

def get_ndigits(arr1):
  darr = (arr1[1:] - arr1[-1]).reshape(-1)
  dmin = np.min(np.abs(darr[darr!=0]))
  return np.maximum(2, int(-np.log10(dmin)) + 2)

def write_keyword(lambs, lamb_names, prefix='fep_opt'):
  assert len(lambs.shape) == 2 and lambs.shape[1] == len(lamb_names)
  for i in range(lambs.shape[0]):
    fout = '%s.%d'%(prefix, i)
    with open(fout, 'w') as fh:
      nd = get_ndigits(lambs)
      fh.write(''.join([('%s %.'+'%d'%nd+'f\n')%(lamb_names[_], lambs[i, _]) for _ in range(lambs.shape[1])]))

def main2():
  func = compute_err_std
  df2 = pd.DataFrame(columns=func(None))
  for f1 in sys.argv[1:]:
    df1 = pd.read_csv(f1, sep='\s+', header=0, index_col=0)
    df2.loc[f1, :] = func(df1)
  print(df2.to_string())
  for col in ('sd_all', 'sd_equ'):
      errs = est_err(df2[col].to_numpy())
      print(col, ' '.join(['%.4f'%_ for _ in errs]))

def main():
  arr = np.loadtxt(sys.argv[1])
  err1 = np.loadtxt(sys.argv[2])
  #print(split_lamb_array(arr))
  lamb_new = adjust_lambs(arr, err1)
  print(lamb_new)
  write_keyword(lamb_new, 'vdw-lambda ele-lambda'.split())
if len(sys.argv) > 3:
  main2()
else:
  main()
