import React, { Component } from 'react'
import { Col } from 'react-bootstrap';
import { SearchkitManager, SearchkitProvider, SearchBox, Hits } from "searchkit";
import Highlighter from "react-highlight-words";

const sk = new SearchkitManager("https://172.17.0.1:9200/kibana_sample_data_ecommerce/", {
  basicAuth:"elastic:elastic",
})

class CustomHits extends Component {

    constructor(props) {
      super(props);
    }

    render() {
      // console.log(this.props.result._source)
        return  <Col lg={{ span: 12 }}>
                  <div style={{border: '2px solid #d1d1d1', marginTop:20, height: 120, backgroundColor: "white", borderRadius: 5, display: 'flex', flexDirection: 'row', alignItems: 'center'}}>
                    <div style={{ marginLeft: 16, marginRight: 16 }}>
                      <img style={{height: 70, width: 70, borderRadius: 35}} alt="" src={"https://static.remove.bg/remove-bg-web/2a274ebbb5879d870a69caae33d94388a88e0e35/assets/start-0e837dcc57769db2306d8d659f53555feb500b3c5d456879b9c843d1872e7baa.jpg"} />
                    </div>
                    <div>
                      <div style={{fontWeight:"bold", fontSize:20}}>
                        <a href="www.google.fr">
                          <Highlighter
                            searchWords={[this.props.queryValue]}
                            textToHighlight={this.props.result._source.customer_first_name}
                            highlightStyle={{backgroundColor: "#fcf403"}}
                          />
                        </a>
                      </div>
                      <div>
                        <Highlighter
                          searchWords={[this.props.queryValue]}
                          textToHighlight={this.props.result._source.email}
                          highlightStyle={{backgroundColor: "#fcf403"}}
                        />
                      </div>
                      <div style={{fontSize:10}}>
                        source:
                      </div>
                      <div style={{fontSize:10}}>
                        sentiment:
                      </div>
                      <div style={{fontSize:10, marginBottom:5}}>
                        {this.props.result._source.email}
                      </div>
                    </div>
                  </div>
                </Col>
    }
}

export class SearchUI extends Component {

    state = {
      queryValue: ""
    }

    queryBuilder = (queryString) => {
        this.setState({queryValue: queryString})
        return {
            "bool": {
                "must": [],
                "filter": [
                  {
                    "multi_match": {
                      "type": "best_fields",
                      "query": queryString,
                      "lenient": true,
                    }
                  },
                  {
                    "range": {
                      "order_date": {
                        "gte": "2016-04-28T13:59:33.997Z",
                        "lte": "2021-07-28T15:00:28.904Z",
                        "format": "strict_date_optional_time"
                      }
                    }
                  }
                ],
                "should": [],
                "must_not": [],
            }
        }
    }
    
    render() {
        return (
          <div style={{display: "flex", flex:1}}>
            <SearchkitProvider searchkit={sk}>
              <div style={{alignItems: "center", display: "flex", width: "100%", marginBottom: 50, flexDirection:"column", marginTop: 50, backgroundColor: '#e6e6e6'}}>
                <div style={{fontSize:30, marginTop: 20}}>
                  Enter any keyword
                </div>
                <div style={{marginTop:15}}>
                  <SearchBox
                    searchOnChange={true}
                    queryBuilder={(queryString) => this.queryBuilder(queryString)}
                  />
                </div>
                <div style={{justifyContent: "center", alignItems: "center", width:"80%", marginTop:50}}>
                  <Hits itemComponent={<CustomHits queryValue={this.state.queryValue}/>}/>
                </div>
              </div>
            </SearchkitProvider>
          </div>
        );
    }
}

export default SearchUI;