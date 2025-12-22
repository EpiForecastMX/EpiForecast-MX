    def clean_dataset(self, df_Alzheimer: pd.DataFrame) -> pd.DataFrame:

        df = df_Alzheimer

        cols_to_drop = conf["limpieza_dataset"]["cols_to_drop"]
        existing = [c for c in cols_to_drop if c in df.columns]
        if existing:
            df = df.drop(columns=existing)


        if "Valor" in df.columns:
            df.loc[:, "Valor"] = (
                df["Valor"].astype(str).str.strip()
                .replace("-", "0")
                .pipe(pd.to_numeric, errors="coerce")
            )

        if "Semana" in df.columns:
            df.loc[:, "Semana"] = (
                df["Semana"].astype(str).str.strip().str.lower()
                .str.replace("sem", "", regex=False)
                .str.replace(" ", "", regex=False)
                .pipe(pd.to_numeric, errors="coerce")
                .astype("Int64")
            )

        if "Entidad" in df.columns:
            df.loc[:, "Entidad"] = (
                df["Entidad"].astype(str).str.strip()
                .replace({"Distrito Federal": "Ciudad de México"})
            )


        if "Ax_003" in df.columns:
            mask_ok = ~df["Ax_003"].astype(str).str.strip().str.lower().eq("acum.")
            df = df.loc[mask_ok, :]


        if "Entidad" in df.columns:
            mask_ok = ~df["Entidad"].astype(str).str.strip().str.upper().eq("TOTAL")
            df = df.loc[mask_ok, :]

        rename_map = {
            "Año": "Year",
            "Semana": "Week",
            "Entidad": "Entity",
            "Ax_001": "Epi_Year",
            "Valor": "Value",
        }

        df = df.rename(columns=rename_map)


        if "Year" in df.columns:
            df.loc[:, "Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")
        if "Week" in df.columns:
            df.loc[:, "Week"] = pd.to_numeric(df["Week"], errors="coerce").astype("Int64")
        if "Epi_Year" in df.columns:
            df.loc[:, "Epi_Year"] = pd.to_numeric(df["Epi_Year"], errors="coerce").astype("Int64")
        if "Value" in df.columns:
            
            val_temp = pd.to_numeric(df["Value"], errors="coerce")
            if pd.Series(val_temp.dropna().apply(float.is_integer)).all():
                df.loc[:, "Value"] = val_temp.astype("Int64")
            else:
                df.loc[:, "Value"] = val_temp


        return df

