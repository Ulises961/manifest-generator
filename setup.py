from setuptools import setup, find_packages

setup(
    name="tool",
    version="0.1",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        'dockerfile-parse',
        'PyYAML',
        'docker',
        'pytest',
        'pytest-cov',
        'mypy',
        'types-PyYAML',
        'types-dockerfile-parse',
        'caseutil',
        'dotenv',
        'click'
        'click-completion',
        'sentence-transformers>=2.2.0',
    ],
    author="Ulises E. Sosa",
    description="A tool for analyzing Docker configurations",
    python_requires=">=3.6",
)