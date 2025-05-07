from setuptools import setup, find_packages

setup(
    name="tool",
    version="0.1",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        'sentence-transformers',
        'scikit-learn',
        'numpy',
        'dockerfile-parse',
        'PyYAML',
        'docker',
        'checkov',
        'pytest',
        'pytest-cov',
        'torch>=2.0.0',
        'mypy',
        'types-PyYAML',
        'types-dockerfile-parse',
        'caseutil',
        'accelerate>=0.26.0',
        'dotenv'],
    author="Ulises E. Sosa",
    description="A tool for analyzing Docker configurations",
    python_requires=">=3.6",
)