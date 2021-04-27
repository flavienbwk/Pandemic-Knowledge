# Pandemic-Knowledge searchkit

React JS app for es data visualization

## Launch
```bash
docker-compose up -d
```
Then go on : 
[searchkit](http://localhost:3000/)

## Config
To manage the elasticsearch host, edit ./src/App.js
```bash
const host = "https://172.17.0.1:9200/"
const searchkit = new SearchkitManager(host, {
	basicAuth: "elastic:elastic",
})
```
