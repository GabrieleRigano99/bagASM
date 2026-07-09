FROM mambaorg/micromamba:1.5-jammy

RUN micromamba install -y -n base -c bioconda -c conda-forge \
        minibwa=0.3 \
        polypolish=0.6.1 \
        samtools=1.23.1 \
    && micromamba clean --all --yes

ENV PATH="/opt/conda/bin:${PATH}"
