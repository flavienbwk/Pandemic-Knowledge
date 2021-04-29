import React, { Component } from 'react'
import packageJson from '../package.json';

export class About extends Component {

    render() {
        return (
            <div>
                <h2>About</h2>
                <p>A fully-featured multi-source data pipeline for continuously extracting knowledge from COVID-19 data.</p>
                <p>If you find an issue or have a suggestion, <a target="_blank" rel="noopener noreferrer" href="https://github.com/flavienbwk/Pandemic-Knowledge">please open an issue on Github</a>.</p>
                <hr />
                <p>Version <b>{packageJson["version"]}</b></p>
            </div>
        )
    }

    componentDidMount() {
        document.title = "About - Pandemic Knowledge";
    }

}
