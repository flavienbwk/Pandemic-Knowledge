import { NotificationManager } from 'react-notifications'

export class Notifier {

    static createNotification = (type, title="", message="", timeout=3000) => {
        switch (type) {
            case 'info':
                NotificationManager.info(message, title, timeout);
                break;
            case 'success':
                NotificationManager.success(message, title, timeout);
                break;
            case 'warning':
                NotificationManager.warning(message, title, timeout);
                break;
            case 'error':
                NotificationManager.error(message, title, timeout)
                break
            default:
                break
        }
    }

    /**
     * From any API response, checks for its
     * validity and displays the appropriate
     * notification depending on whether there
     * is an error or not.
     * 
     * If there is an API call fatal error (response
     * gets undefined), default_error_message is
     * displayed. Else, the API's message is
     * the one displayed.
     */
    static notifyFromResponse = (
        api_response,
        default_title,
        default_error_title="An error occured",
        default_error_message="Query failed"
    ) => {
        let type = "error"
        let title = default_error_title
        let message = default_error_message
        if (api_response) {
            title = default_title
            message = ("message" in api_response) ? api_response.message : ""
            type = ("error" in api_response && api_response.error) ? "error" : "success"
        }
        Notifier.createNotification(type, title, message)
    }
        

}