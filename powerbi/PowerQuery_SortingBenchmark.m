// Power BI Desktop > Transform data > Advanced Editor. Change the file path below.
let
    Source = Csv.Document(File.Contents("C:\SortingLab\results\powerbi\all_datasets_benchmark.csv"),[Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source,[PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted,{{"run_id",type text},{"run_utc",type datetimezone},{"dataset",type text},{"sha256",type text},{"column",type text},{"algorithm",type text},{"n",Int64.Type},{"repeats",Int64.Type},{"median_ms",type number},{"min_ms",type number},{"max_ms",type number},{"peak_kb",type number},{"status",type text},{"reason",type text}})
in
    Typed
