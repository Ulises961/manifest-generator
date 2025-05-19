#!/bin/bash
#SBATCH -p edu-thesis
#SBATCH --gres=gpu:4
#SBATCH --mem=120G
#SBATCH --cpus-per-task=16
#SBATCH --ntasks=1
#SBATCH --time=00:20:00
#SBATCH --job-name=k8s-infer
#SBATCH --output=logs/k8s-infer-%j.out
#SBATCH -N 1

module load Python/3.11.3-GCCcore-12.3.0

source venv/bin/activate

accelerate launch --multi_gpu src/main.py





