from .home import index
from .controller import controller_reset_view
from .brewery import brewery_list_view, brewery_delete_view
from .sensor import sensor_detail_view, sensor_cleanup_view
from .recipe import recipe_list_view, recipe_create_view, recipe_edit_view, recipe_delete_view
from .session import brew_session_list_view, brew_session_create_view, brew_session_detail_view, brew_session_delete_view, brew_session_cancel_view
from .settings import brewery_settings_view, controller_settings_view
from .manual import manual_control_view
from .direct import direct_control_view
