/**
 * Checks if the API is live.
 */
export class Ping {

    /**
     * Returns the API response of the route
     * dedicated to answer to a simple ping.
     */
    static pingApi = () => {
        return fetch("http://localhost:5000/api")
            .then(res => res.json())
            .then((data) => { return data })
            .catch(console.error)
    }

}