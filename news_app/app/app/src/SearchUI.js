import React, { Component } from 'react';
import { Row, Col, Card } from 'react-bootstrap';
import { SearchkitManager, SearchkitProvider, SearchBox, Hits } from 'searchkit';
import Highlighter from 'react-highlight-words';

const search_kit = new SearchkitManager('https://172.17.0.1:9200/news_*/', {
	basicAuth: 'elastic:elastic'
});

export class SearchUI extends Component {
	state = {
		queryValue: ''
	};

	queryBuilder = (queryString) => {
		this.setState({ queryValue: queryString });
		return {
			bool: {
				must: [],
				filter: [
					{
						multi_match: {
							type: 'best_fields',
							query: queryString,
							lenient: true
						}
					}
				],
				should: [],
				must_not: []
			}
		};
	};

	render() {
		return (
			<SearchkitProvider searchkit={search_kit}>
				<div>
					<Row>
						<Col lg={{ span: 12 }} className="pt-4 pb-4">
							<SearchBox
								translations={{ 'searchbox.placeholder': 'Search COVID-related news' }}
								autofocus={true}
								className={'form-control'}
								searchOnChange={true}
								queryBuilder={this.queryBuilder}
							/>
						</Col>
					</Row>
					<Row>
						<Hits hitsPerPage={8} itemComponent={<News queryValue={this.state.queryValue} />} />
					</Row>
				</div>
			</SearchkitProvider>
		);
	}
}

class News extends Component {
	render() {
		return (
			<Row className="mt-2"
				onClick={() => {
					window.open(this.props.result._source.link)
				}}
				style={{
					cursor: "pointer"
				}}
				title={this.props.result._source.link}
			>
				<Col lg={{ span: 2 }}>{<img style={{ width: '100%' }} src={this.props.result._source.img} />}</Col>
				<Col lg={{ span: 8 }}>
					<Card>
						<Card.Body>
							<Card.Title>
								<Highlighter
									searchWords={[this.props.queryValue]}
									textToHighlight={this.props.result._source.title}
									highlightStyle={{ backgroundColor: '#fcf403' }}
								/>
								<br />
								{
									(this.props.result._source.date)
										?
										<small>
											<b>{new Date(this.props.result._source.date).toLocaleDateString('fr-FR')}</b>
										</small>
										: <></>
								}
							</Card.Title>
							<Card.Text>
								<Highlighter
									searchWords={[this.props.queryValue]}
									textToHighlight={this.props.result._source.desc}
									highlightStyle={{ backgroundColor: '#fcf403' }}
								/>
							</Card.Text>
						</Card.Body>
					</Card>
				</Col>
			</Row>
		);
	}
}

export default SearchUI;
