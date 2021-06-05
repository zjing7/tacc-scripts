#!/bin/bash
# the project id
#SBATCH -A MCB21006
# the queue
#SBATCH -p rtx-dev
# num nodes
#SBATCH -N 1
# num tasks
#SBATCH -n 1
# num tasks per node
#SBATCH --tasks-per-node 1
# max running time
#SBATCH -t 01:00:00
#SBATCH -J test_tinkerHP

##################################### MODULE loading (same as what was used when compiling THP) ########################################

module purge
module load cuda/11.0 tacc-singularity

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
svfreq=1.0

# timestep (fs)
dt=10.0

# 1 ns total simulation time
nsteps=100000

############################################# RUN TINKER-HP here ################################

export TACC_IBRUN_DEBUG=1
export TACC_AFFINITY_DEBUG=1

# This is the singularity image: it is a self-contained containerized linux environmenent providing Tinker-HP and its dependencies
export SIF_EXEC="/home1/08036/fhedin/WORK2/deploy/atlas/Tinker-HP/tinker-hp-21.05.sif"

# inside the singularity sif container are available the following executables under /home/tinker/bin:
# $ singularity exec tinker-hp-21.05.sif ls -lrth /home/tinker/bin/
# total 417M
# -rwxr-xr-x 1 root root 105M May 18 11:54 minimize.gmix
# -rwxr-xr-x 1 root root 108M May 18 11:54 dynamic.gmix
# -rwxr-xr-x 1 root root 103M May 18 11:54 analyze.gmix
# -rwxr-xr-x 1 root root 102M May 18 11:54 bar.gmix

# gmix are GPU releases compiled in mixed precision, optimized for the following compute capabilities : CC60 CC70 CC80

# we launch the job using the ibrun wrapper around srun
#  the first args are the singularity command and its exec argument
#  then come some singularity options: the local watersmall directory is mounted into the container at /tmp/watersmall using --bind
#  and the runtime dir is set to /tmp/watersmall using --pwd
#  --nv makes host GPUs accessible from within the container
#  then comes the path to the .sif container
#  and in the end the absolute path to Tinker-HP within the container (see above) and the comand line parameters to Tinker-HP
ibrun singularity exec --bind $PWD/watersmall:/tmp/watersmall --pwd /tmp/watersmall --nv $SIF_EXEC /home/tinker/bin/dynamic.gmix watersmall $nsteps $dt $svfreq $ensemble $temp $pressure

# the output dyn and dcd files are available within the shared directory watersmall

