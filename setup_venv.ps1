$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.21.9-hotspot"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
$env:HADOOP_HOME = "C:\hadoop"
$env:PATH = "$env:HADOOP_HOME\bin;$env:PATH"

$env:VINF_WIKI_DUMP = "C:\Users\adamp\Skola\Ing\ZS1\VINF\wiki_dump\enwiki-latest-pages-articles.xml.bz2"
$env:VINF_SPARK_DRIVER_MEMORY = "8g"
$env:VINF_SPARK_TMP = "C:\spark-tmp"

Remove-Item -Recurse -Force write_test_out -ErrorAction SilentlyContinue