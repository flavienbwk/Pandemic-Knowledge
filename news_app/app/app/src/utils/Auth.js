import { Cookies } from 'react-cookie'
import { Notifier } from './Notifier'
import { User } from './User'

export class Auth {

    constructor(onAuthUpdateCallbacks = [() => {}]) {
        this.cookies = new Cookies()
        this.api_endpoint = "http://localhost:5000/api"
        this.onAuthUpdateCallbacks = onAuthUpdateCallbacks // Callbacked if any update has been done to the "authentication" token
    }

    /**
     * Triggers the list of callbacks provided in the constructor.
     */
    onAuthUpdateCallback() {
        for (var callback of this.onAuthUpdateCallbacks)
            callback()
    }

    /**
     * Returns true on valid user authentication.
     * 
     * Returns false on cookie missing or invalid properties.
     */
    isUserAuthenticated() {
        const cookie = this.cookies.get("authentication")
        if (cookie && "authenticated" in cookie)
            return cookie.authenticated
        else
            return false
    }

    /**
     * Returns false on cookie missing or invalid properties
     */
    getUserProfile() {
        return this.cookies.get("profile")
    }

    /**
     * If user was successfuly authenticated by the API,
     * will register cookies including its connection
     * token and profile details.
     */
    registerUserAuthentication = async (api_auth_query) => {
        if (api_auth_query) {
            if ("error" in api_auth_query && api_auth_query.error === false) {
                // Save auth token
                this.cookies.set("authentication", {
                    "authenticated": true,
                    "token": api_auth_query.details.token,
                    "expires_at": api_auth_query.details.expires_at
                })
                await this.updateUserProfile()
                this.onAuthUpdateCallback()
            }
            Notifier.notifyFromResponse(api_auth_query, "Authentication")
        } else {
            Notifier.createNotification(
                "error",
                "Authentication",
                "Error while saving your session in your browser"
            )
        }
    }

    updateUserProfile = async () => {
        const user_profile_query = await User.requestUserProfile()
        if (user_profile_query) {
            if ("error" in user_profile_query && user_profile_query.error === false) {
                this.cookies.set("profile", {
                    "ids": user_profile_query.details.ids,
                    "username": user_profile_query.details.username,
                    "first_name": user_profile_query.details.first_name,
                    "last_name": user_profile_query.details.last_name,
                    "email": ("email" in user_profile_query.details) ? user_profile_query.details.email : "",
                    "updated_at": user_profile_query.details.updated_at,
                })
                this.onAuthUpdateCallback()
            } else {
                Notifier.notifyFromResponse(user_profile_query, "Profile details")
            }
        } else {
            Notifier.createNotification(
                "error",
                "Profile details",
                "Failed to retrieve your profile details"
            )
        }
    }

    /**
     * Request an API call to delete token and destroys 
     * the "authentication" and "profile" cookies.
     */
    logoutUser = async () => {
        const user_cookie = this.cookies.get("authentication")
        if (user_cookie) {
            if ("token" in user_cookie) {
                const logout_query = await this.#requestUserLogout(user_cookie["token"])
                if ("error" in logout_query && logout_query.error) {
                    Notifier.notifyFromResponse(logout_query, "Server logout")
                }
            }
            this.cookies.remove("authentication")
            this.cookies.remove("profile")
            Notifier.createNotification(
                "success",
                "Client logout",
                "Successfuly logged you out"
            )
            this.onAuthUpdateCallback()
        }
    }

    /**
     * Returns the API response for LDAP authentication
     */
    #requestUserLogout = (token_value) => {
        return fetch(this.api_endpoint + "/auth/logout", {
            method: "POST",
            headers: { 'X-Api-Auth-Token': token_value }
        })
        .then(res => res.json())
        .then((data) => { return data })
        .catch(console.error)
    }

    /**
     * Updates the user authentication cookies 
     * depending on token presence and validity.
     * 
     * Returns the validity status of the token. 
     */
    checkUserToken = async () => {
        let user_authenticated = false
        let auth_cookie = this.cookies.get("authentication")
        if (auth_cookie 
            && "token" in auth_cookie 
            && "authenticated" in auth_cookie 
            && auth_cookie["authenticated"]) {
            const api_check = await this.#requestLoginCheck(auth_cookie.token)
            if (api_check === undefined || api_check.error) {
                Notifier.notifyFromResponse(api_check, "Token check", "Token check failure")
                auth_cookie = {
                    "authenticated": false,
                    "token": "",
                    "expires_at": 0
                }
            } else {
                auth_cookie["authenticated"] = true
                auth_cookie["expires_at"] = api_check.details.expires_at
                user_authenticated = true
            }
            this.cookies.set("authentication", auth_cookie)
            this.onAuthUpdateCallback()
        }
        return user_authenticated
    }

    /**
     * Returns the API response for LDAP authentication
     */
    requestLDAPLogin = (username, password) => {
        return fetch(this.api_endpoint + "/auth/ldap/login", {
            method: "POST",
            headers: { 'Content-Type': "application/json" },
            body: JSON.stringify({
                "username": username,
                "password": password
            })
        })
        .then(res => res.json())
        .then((data) => { return data })
        .catch(console.error)
    }

    /**
     * Returns the API response for LDAP authentication
     */
    #requestLoginCheck = (token_value) => {
        return fetch(this.api_endpoint + "/auth/check", {
            method: "POST",
            headers: { 'X-Api-Auth-Token': token_value }
        })
        .then(res => res.json())
        .then((data) => { return data })
        .catch(console.error)
    }

}