import React, { Component } from 'react'
import { HashRouter as Router, Route, Switch } from 'react-router-dom'
import { NotificationContainer } from 'react-notifications'
import { NavigationBar } from './NavigationBar'
import { Layout } from './Layout'
import Home from './Home'
import { About } from './About'
import packageJson from '../package.json'

export class App extends Component {

    /**
     * Child components may trigger this parent event to
     * inform other routes (<NavigationBar> for example),
     * that authentication information have been updated.
     * 
     * This allows to show the "Login" or "Logout" button
     * depending on user's authentication status.
     */
    onAuthUpdate = () => {}

    render() {
            return (
            <React.Fragment>
                <Router basename={packageJson["homepage"] + "/"}>
                    <NotificationContainer />
                        <NavigationBar />
                    <Layout>
                        <Switch>
                            <Route exact path="/" component={Home} />
                            <Route path="/about" component={About} />
                        </Switch>
                    </Layout>
                </Router>
            </React.Fragment>
        )
    }
}

export default App
