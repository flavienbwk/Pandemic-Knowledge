import { Cookies } from 'react-cookie'

/**
 * User-related operations
 */
export class User {

    /**
     * Returns the API response for user profile details
     */
    static requestUserProfile = () => {
        const cookies = new Cookies()
        const user_cookie = cookies.get("authentication")
        if (user_cookie && "token" in user_cookie) {
            return fetch("http://localhost:5000/api/user/profile", {
                method: "POST",
                headers: { 'X-Api-Auth-Token': user_cookie["token"] }
            })
            .then(res => res.json())
            .then((data) => { return data })
            .catch(console.error)
        }
        return null
    }

    /**
     * Updates the user details. For the example, only
     * working for "emails".
     */
    static updateUserProfile = (profile_payload) => {
        const cookies = new Cookies()
        const user_cookie = cookies.get("authentication")
        if (user_cookie && "token" in user_cookie) {
            return fetch("http://localhost:5000/api/user/profile", {
                method: "PUT",
                headers: { 
                    'X-Api-Auth-Token': user_cookie["token"],
                    'Content-Type': "application/json"
                },
                body: JSON.stringify(profile_payload)
            })
            .then(res => res.json())
            .then((data) => { return data })
            .catch(console.error)
        }
        return null
    }

}