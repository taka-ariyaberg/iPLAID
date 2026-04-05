import pandas as pd


def extract_compound_info(text):
    try:
        result = pd.Series(text.str.extract(r'^(.+)\[(.+)\]$').values.ravel())
    except ValueError:
        result = pd.Series(['', ''])
    return result


def logtodf(logfile):
    import pandas as pd

    log = pd.read_csv(logfile, sep=',', header=None)
    delimiter = '\t'
    df2 = log[0].str.split(delimiter, expand=True)
    df2 = df2.apply(lambda x: x.str.strip() if x.dtype == "object" else x)

    plates = df2[df2[0].str.startswith('Target')][0].str.extract(r"\:(.*?)\(")
    plates = plates[0].str.strip().tolist()
    print(plates)

    end = [int(df2.tail(1).index.item())]
    split = df2.index[df2[0] == "Liquid"].tolist()
    startprot = [i for i in split]
    endprot = startprot[1:]
    endprot = [i - 3 for i in endprot]
    endprot = endprot + end

    masterdf = []

    for i, stindex in enumerate(startprot):
        start = startprot[i] + 1
        end = endprot[i] + 1

        df = df2[start:end].copy()
        df["Target Plate"] = plates[i]
        masterdf.append(df)

    df = pd.concat(masterdf)

    df.columns = [
        "Liquid Name", "Source", "Target Well", "TargetFwd", "TargetSide",
        "Drop", "Miss", "TargetVolume", "DosingEnergy", "Target Plate"
    ]
    df["Miss"] = pd.to_numeric(df["Miss"])
    df["Drop"] = pd.to_numeric(df["Drop"])

    df[["TargetVolume", "TargetUnit"]] = df["TargetVolume"].str.split(" ", expand=True)
    df["TargetVolume"] = pd.to_numeric(df["TargetVolume"])

    df = df.loc[df["Target Well"] != "Waste"]

    return df
