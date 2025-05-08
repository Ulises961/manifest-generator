# How to use
1. Clone the repository and access to its root
3. Generate a python venv `python3 -m venv ./venv`
4. Open a shell and activate the environment ` source venv/bin/activate`
5. Install the dependencies `pip install -r requirements.txt`
6. Install the project as a package `pip install -e .` 
7. Clone the [microservices-demo](https://github.com/GoogleCloudPlatform/microservices-demo/tree/main) locally. 
8. In the src/main.py, manually set up the path to the microservices-demo repository 
9. Launch the parser: `python src/main.py`

As a result a target/ folder will be generated together with a src/logs/ folder within the project