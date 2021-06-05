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
#SBATCH -t 1:00:00
# send email notifications
#SBATCH -J fep-0

##################################### MODULE loading (same as what was used when compiling THP) ########################################
module purge
module load cuda/11.0 tacc-singularity

###################################### PATH to TIBKER-HP exec and to the wrapper env script if required ##############################

export thp_exec="$PWD/bin/dynamic.gmix"
export thp_bar="$PWD/bin/bar.gmix"
export thp_analyze="$PWD/bin/analyze.gmix"
export thp_wrapper="/bin/bash $PWD/wrapper.sh"
export thp_wrapper_bar="/bin/bash $PWD/wrapper_bar.sh"

##################################### TINKER-HP PARAMS ########################################

simname=fxr

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
nsteps=1200000

############################################# RUN TINKER-HP here ################################

export TACC_IBRUN_DEBUG=1
export TACC_AFFINITY_DEBUG=1

export SIF_EXEC="/work2/08036/fhedin/frontera/deploy/atlas/Tinker-HP/tinker-hp-21.05.sif"
export SIF_EXEC="/home1/03760/zj2244/Software/tinkerhp/2021-06-01/tinker-hp-runtime-21.05.sif"

PROCESS_ID=$$

# this is how we can run 4 jobs per node
#  see : ibrun --help
#  or  : https://frontera-portal.tacc.utexas.edu/user-guide/launching/#more-than-one-mpi-application-running-concurrently

# the -o will result in a ibrun_o_option env.var. to be generated and offseted by 1 ;
# internally each Tinker-HP instance is attached to a GPU based on the value of PGI_ACC_DEVICE_NUM which is set in wrapper.sh
# based on ibrun_o_option so that each instance will use a different GPU for optimal performance

#inputs="FXR-89/solv/run1/solv-05 FXR-89/solv/run1/solv-06 FXR-89/solv/run1/solv-07 FXR-89/solv/run1/solv-08"
#inputs="FXR-89/solv/run1/solv-20 FXR-89/solv/run1/solv-21 FXR-89/solv/run1/solv-22 FXR-89/solv/run1/solv-23 FXR-89/solv/run1/solv-24 FXR-89/solv/run1/solv-25 FXR-89/solv/run1/solv-26"
inputs="FXR-89/solv/run1/solv-16 FXR-89/solv/run1/solv-17 FXR-89/solv/run1/solv-18 FXR-89/solv/run1/solv-19 FXR-89/solv/run1/solv-20 FXR-89/solv/run1/solv-21 FXR-89/solv/run1/solv-22 FXR-89/solv/run1/solv-23 FXR-89/solv/run1/solv-24 FXR-89/solv/run1/solv-25 FXR-89/solv/run1/solv-26"

function run_fep {
  inputdir=$1
	iproc=$2
	igpu=$(( $iproc % 4 ))

	scratchdir=$SCRATCH/FEP-${PROCESS_ID}-${iproc}
	dir2=/tmp/FEP-${PROCESS_ID}-${iproc}
	export SINGULARITYENV_CUDA_VISIBLE_DEVICES=$igpu

	mkdir -p $scratchdir
	rsync -a $inputdir/* $scratchdir/

  ibrun -n 1 -o $iproc /usr/local/bin/task_affinity singularity exec --bind $scratchdir:$dir2 --pwd $dir2 --nv $SIF_EXEC /home/tinker/bin/dynamic.gmix $simname $nsteps $dt $svfreq $ensemble $temp $pressure &> $scratchdir/md.log 
  if [ -f $scratchdir/fep-4.key ] ; then
    #ibrun -n 1 -o $offset /usr/local/bin/task_affinity $thp_wrapper $thp_bar 1 $i/fep-4 $temp $i/fep-5 $temp &> $i/bar1-4-5.out &
    ibrun -n 1 -o $offset /usr/local/bin/task_affinity singularity exec --bind $scratchdir:$dir2 --pwd $dir2 --nv $SIF_EXEC /home/tinker/bin/bar.gmix 1 fep-4 $temp fep-5 $temp &> $scratchdir/bar1-4-5.out &
    #$thp_wrapper_bar "ibrun -n 1 -o $offset /usr/local/bin/task_affinity $thp_wrapper $thp_analyze" $i/fep-4.dcd $temp $i/fep-5.dcd $temp &> $i/bar1-4-5.out &
  fi
  if [ -f $scratchdir/fep-6.key ] ; then
    ibrun -n 1 -o $offset /usr/local/bin/task_affinity singularity exec --bind $scratchdir:$dir2 --pwd $dir2 --nv $SIF_EXEC /home/tinker/bin/bar.gmix 1 fep-5 $temp fep-6 $temp &> $scratchdir/bar1-5-6.out &
	fi
	wait

  if [ -f $scratchdir/fep-6.key ] ; then
	  rm $scratchdir/${simname}.dcd $scratchdir/${simname}.arc | true
	fi

	cp $scratchdir/* $i/
}
function get_min_key {
  kfile1=$1
  kfile2=$2
	if [ -f "$kfile1" ] ; then
	grep -v -e "^DSHORT" -e "DINTER" -e "POLAR-ALG" $kfile1 > $kfile2
	fi
}
function run_minimize {
  inputdir=$1
	iproc=$2
	igpu=$(( $iproc % 4 ))
	export SINGULARITYENV_CUDA_VISIBLE_DEVICES=$igpu
	scratchdir=$inputdir
	dir2=/tmp/equ-${PROCESS_ID}-${iproc}
	flog1=$scratchdir/md.log
	if [ -f $flog1 ] && [ `grep "Short Induce PCG solver not converged" $flog1 -c ` -ge 1 ] ; then
	get_min_key $scratchdir/tinker.key  $scratchdir/tinker0.key
	mv $scratchdir/${simname}.xyz $scratchdir/${simname}.xyz_0
  ibrun -n 1 -o $iproc /usr/local/bin/task_affinity singularity exec --bind $scratchdir:$dir2 --pwd $dir2 --nv $SIF_EXEC /home/tinker/bin/minimize.gmix ${simname}.xyz_0 10.0 -k tinker0.key &> $scratchdir/min.log 
	fi
}

offset=0
for i in $inputs ; do
	#run_fep $i $offset &
	#run_minimize $i $offset &
	igpu=$(( $offset % 4 ))
	run_minimize $i $igpu  &
  (( offset++ ))
	if [ $igpu -eq 3 ] ; then
	  wait
	fi
done

wait

