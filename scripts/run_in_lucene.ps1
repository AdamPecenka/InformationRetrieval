# Runs a python script from this repo inside the PyLucene container.
#   .\scripts\run_in_lucene.ps1 main.py lucene-index
# The repo (including data/) is mounted at /work, so files written there appear on the host.
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs
)

$Image = "coady/pylucene:10.0.0"

docker run --rm -it `
    -v "${PWD}:/work" `
    -w /work `
    -e PYTHONPATH=/work `
    -e PYTHONUTF8=1 `
    $Image python @ScriptArgs