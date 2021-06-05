#!/bin/bash
# the project id
#SBATCH -A MCB21004
# the queue
#SBATCH -p rtx
# num nodes
#SBATCH -N 1
# num tasks
#SBATCH -n 4
# num tasks per node
#SBATCH --tasks-per-node 4
# max running time
#SBATCH -t 15:00:00
# send email notifications
#SBATCH -J fep-@id

##################################### MODULE loading (same as what was used when compiling THP) ########################################

module purge
module load pgi/20.7.0 cuda/11.0 pmix/3.1.4 ucx/1.6.1
module li

export PATH=/opt/apps/pgi/20.7.0/Linux_x86_64/20.7/comm_libs/mpi/bin:$PATH
export MKLROOT=/opt/intel/compilers_and_libraries_2020.1.217/linux/mkl
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$MKLROOT/lib/intel64/

###################################### PATH to TIBKER-HP exec and to the wrapper env script if required ##############################

export thp_exec="$PWD/bin/dynamic.gmix"
export thp_bar="$PWD/bin/bar.gmix"
export thp_analyze="$PWD/bin/analyze.gmix"
export thp_wrapper="/bin/bash $PWD/wrapper.sh"
export thp_wrapper_bar="/bin/bash $PWD/wrapper_bar.sh"

##################################### TINKER-HP PARAMS ########################################

# type of ensemble (2=NVT 4=NPT)
ensemble="2"
# ensemble="4"

# temperature (K)
temp=300.0 

#pressure in atm
pressure=""
# pressure=1.0

#IO freq in ps
svfreq=2.0

# timestep (fs)
dt=10.0

# 5 ns total simulation time
nsteps=2000000

############################################# RUN TINKER-HP here ################################

export TACC_IBRUN_DEBUG=1
export TACC_AFFINITY_DEBUG=1

# this is how we can run 4 jobs per node
#  see : ibrun --help
#  or  : https://frontera-portal.tacc.utexas.edu/user-guide/launching/#more-than-one-mpi-application-running-concurrently

# the -o will result in a ibrun_o_option env.var. to be generated and offseted by 1 ;
# internally each Tinker-HP instance is attached to a GPU based on the value of PGI_ACC_DEVICE_NUM which is set in wrapper.sh
# based on ibrun_o_option so that each instance will use a different GPU for optimal performance

inputs="@inputs"

offset=0
for i in $inputs ; do
  ibrun -n 1 -o $offset /usr/local/bin/task_affinity $thp_wrapper $thp_exec $i/fxr $nsteps $dt $svfreq $ensemble $temp $pressure &> $i/md.log &
  (( offset++ ))
done

wait

offset=0
for i in $inputs ; do
  if [ -f $i/fep-4.key ] ; then
    ibrun -n 1 -o $offset /usr/local/bin/task_affinity $thp_wrapper $thp_bar 1 $i/fep-4 $temp $i/fep-5 $temp &> $i/bar1-4-5.out &
    #$thp_wrapper_bar "ibrun -n 1 -o $offset /usr/local/bin/task_affinity $thp_wrapper $thp_analyze" $i/fep-4.dcd $temp $i/fep-5.dcd $temp &> $i/bar1-4-5.out &
  fi
  if [ -f $i/fep-6.key ] ; then
    ibrun -n 1 -o $offset /usr/local/bin/task_affinity $thp_wrapper $thp_bar 1 $i/fep-5 $temp $i/fep-6 $temp &> $i/bar1-5-6.out &
    #$thp_wrapper_bar "ibrun -n 1 -o $offset /usr/local/bin/task_affinity $thp_analyze" $i/fep-5.dcd $temp $i/fep-6.dcd $temp &> $i/bar1-5-6.out &
  else
    echo "Remove traj @ $i ?"
  fi
  (( offset++ ))
done
wait
