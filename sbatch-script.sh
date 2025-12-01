#!/bin/bash
#if minikube is not running start it
if ! minikube status &> /dev/null; then
    minikube start
fi
# Set the context to minikube
eval $(minikube docker-env)

