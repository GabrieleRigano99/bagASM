FROM mambaorg/micromamba:1.5-jammy

RUN micromamba install -y -n base -c bioconda -c conda-forge \
        minimap2=2.30 \
        racon=1.5.0 \
        samtools=1.23.1 \
    && micromamba clean --all --yes

ENV PATH="/opt/conda/bin:${PATH}"
