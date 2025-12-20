# lexical-variation

## Running the experiment

The experiment is created using Empirica. You need to install it: 

```bash
curl -fsS https://install.empirica.dev | sh
```

To run the experiment locally: 

```bash
cd experiment
empirica
```

## Dependencies

The R packages are managed by `renv` and the Python packages are managed by conda.

The R version is `4.5.2`.

```bash
conda env create -f environment.yml
conda activate lexical-variation
renv::restore()
```