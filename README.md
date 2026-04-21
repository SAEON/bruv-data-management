# BRUV Data Workflow – SAEON & SAIAB Collaboration

## Overview

This repository documents a collaborative effort between the **South African Environmental Observation Network (SAEON)** and the **South African Institute for Aquatic Biodiversity (SAIAB)** to develop workflows for managing and publishing **Baited Remote Underwater Video (BRUV)** biodiversity data.

The project focuses on establishing a data pipeline that enables BRUV observations to move from local databases into **Specify 7**, and ultimately be published to the **Global Biodiversity Information Facility (GBIF)**.

The work supports open biodiversity data, improves data management practices, and contributes to strengthening national biodiversity observation systems.

---

## Objectives

The main objectives of this project are:

- Develop workflows for managing **BRUV biodiversity observation data**
- Deploy **Specify 7** as a biodiversity data management platform
- Integrate local biodiversity databases with Specify using APIs or service endpoints
- Establish structured data pipelines to prepare datasets for publication
- Enable the publication of curated biodiversity records to **GBIF**
- Support interoperable and open biodiversity data infrastructure in South Africa

---

## Collaboration

This work is being developed through collaboration between:

**SAEON (South African Environmental Observation Network)**  
Responsible for environmental observation infrastructure, data systems, and open data platforms.

**SAIAB (South African Institute for Aquatic Biodiversity)**  
Providing biodiversity expertise, datasets, and domain knowledge for biodiversity monitoring.

Together, the institutions are developing practical workflows that support biodiversity data mobilisation and international interoperability.

---

## Data Source: BRUV

**BRUV (Baited Remote Underwater Video)** systems are used to collect underwater biodiversity observations.  
These systems allow researchers to observe marine species in situ without intrusive sampling methods.

Typical BRUV datasets include:

- species observations
- time-stamped video events
- sampling location information
- environmental metadata
- sampling effort details

Managing these datasets requires structured workflows to ensure data quality, consistency, and interoperability.

---

## System Workflow

The overall workflow being developed follows several stages:

1. **Data Collection**
   - BRUV deployments capture video-based biodiversity observations.

2. **Local Data Storage**
   - Observations and metadata are stored in a local database.

3. **Data Preparation**
   - Data are cleaned, validated, and transformed into structured formats.

4. **Specify 7 Integration**
   - Data are loaded into **Specify 7** using API endpoints or ingestion workflows.

5. **Data Curation**
   - Records are reviewed and managed within the Specify collections management system.

6. **GBIF Publication**
   - Curated datasets are prepared for publication via **GBIF-compatible standards**.

---

## Architecture

The architecture typically includes:

- **Specify 7 server deployment**
- **Local biodiversity database**
- **Data transformation and validation scripts**
- **API or endpoint-based ingestion workflows**
- **Publishing infrastructure for GBIF integration**

This layered architecture supports modular workflows and allows datasets to move from field collection systems to global biodiversity platforms.

---

## Repository Purpose

This repository provides documentation and configuration examples for:

- Deploying **Specify 7** on a server
- Connecting local biodiversity databases
- Developing ingestion workflows
- Supporting data transformation pipelines
- Preparing datasets for **GBIF publication**

The goal is to create a reproducible workflow that can be adapted for other biodiversity observation systems.

---

## Future Development

Future work may include:

- automated ingestion pipelines
- validation tools for biodiversity records
- Darwin Core data transformation workflows
- automated GBIF publishing pipelines
- improved integration with national biodiversity data platforms

---

