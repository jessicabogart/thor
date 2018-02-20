from setuptools import setup

setup(
   name="RaSCaLS",
   version="0.1.2.dev0",
   description="Range, Shift, Cluster and Link Scheme",
   license="BSD 3-Clause License",
   author="Joachim Moeyens, Mario Juric",
   author_email="moeyensj@uw.edu",
   url="https://github.com/moeyensj/RaSCaLS",
   packages=["RaSCaLS"],
   package_dir={"RaSCaLS": "rascals"},
   package_data={"RaSCaLS": ["data/*.orb",
                             "tests/data/*"]},
   setup_requires=["pytest-runner"],
   tests_require=["pytest"],
)
