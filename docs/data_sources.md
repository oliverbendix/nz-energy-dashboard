# Data Sources

This project uses open New Zealand electricity datasets. Below is a concise reference of what each source contains, update cadence, format, and licence.

---

## 1) MBIE — Electricity statistics (quarterly tables)

- **Source**: MBIE “Electricity statistics” website
 https://www.mbie.govt.nz/building-and-energy/energy-and-natural-resources/energy-statistics-and-modelling/energy-statistics/electricity-statistics  
- **Direct file (current June 2025 version)**:  
  https://www.mbie.govt.nz/assets/Data-Files/Energy/nz-energy-quarterly-and-energy-in-nz/electricity-june-2025-q2.xlsx 
- **What it contains**: Latest electricity **generation and demand** tables for New Zealand (aggregated, by fuel type and time period).  
- **Update frequency**: MBIE notes these tables are **updated quarterly**.  
- **Format**: Excel (XLSX); can be read directly in Python for transformation.  
- **Licence**: Creative Commons Attribution 3.0 New Zealand (CC BY 3.0 NZ).  

---

## 2) Electricity Authority (EMI) — Generation_MD (monthly, plant-level)

- **SOurce**: EMI datasets → *Generation output by plant* (**Generation_MD**).  https://www.emi.ea.govt.nz/Wholesale/Datasets/Generation/Generation_MD
- **What it contains**: Plant-level generation **by trading period (half-hour)** and **fuel code**, with monthly CSV files; units are **kilowatt hours** in the monthly files.  
- **Granularity**: Half-hourly trading periods, aggregated into monthly CSVs.  
- **Format**: CSV (one file per month).  
- **Notes**: Web UI lists files; download links are accessible for scripting.  
- **Dataset details**: Units and description per EMI’s About Datasets note. 
- **Licence**: