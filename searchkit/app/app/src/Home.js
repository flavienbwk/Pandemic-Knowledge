import React, { Component } from 'react';
import { Container, Row, Col } from 'react-bootstrap';
import styled from 'styled-components';
import SearchUI from './SearchUI';

const Styles = styled.div`
	.paddind-bottom {
		padding-bottom: 16px;
	}
`;

class Home extends Component {
	render() {
		return (
			<Styles>
				<Container fluid>
					<Row className="paddind-bottom">
						<Col lg={{ span: 12 }}>
							<SearchUI />
						</Col>
					</Row>
				</Container>
			</Styles>
		);
	}

	componentDidMount() {
		document.title = 'Search - Pandemic Knowledge';
	}
}

export default Home;
