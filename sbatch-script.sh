#!/bin/bash
#SBATCH -p edu-thesis
#SBATCH --gres=gpu:a30.24:4
#SBATCH --mem=120G
#SBATCH --cpus-per-task=16
#SBATCH --ntasks=1
#SBATCH --time=02:00:00
#SBATCH --job-name=k8s-infer
#SBATCH --output=logs/k8s-infer-%j.out
#SBATCH -N 1

source venv/bin/activate

python src/main.py





