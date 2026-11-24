# Copy to scripts/setup_venv.ps1 (git-ignored), fill in your paths, then run it:
#   .\scripts\setup_venv.ps1
# Needed only for the Spark stages (wiki-*, lucene-export).
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
# Must contain bin\winutils.exe (and hadoop.dll).
$env:HADOOP_HOME = "C:\hadoop"
$env:PATH = "$env:HADOOP_HOME\bin;$env:PATH"

$env:VINF_WIKI_DUMP = "C:\path\to\enwiki-latest-pages-articles.xml.bz2"
$env:VINF_SPARK_DRIVER_MEMORY = "8g"
$env:VINF_SPARK_TMP = "C:\spark-tmp"
