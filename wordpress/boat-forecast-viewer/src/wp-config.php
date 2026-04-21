<?php
/**
 * The base configuration for WordPress
 *
 * The wp-config.php creation script uses this file during the installation.
 * You don't have to use the website, you can copy this file to "wp-config.php"
 * and fill in the values.
 *
 * This file contains the following configurations:
 *
 * * Database settings
 * * Secret keys
 * * Database table prefix
 * * ABSPATH
 *
 * @link https://developer.wordpress.org/advanced-administration/wordpress/wp-config/
 *
 * @package WordPress
 */

// ** Database settings - You can get this info from your web host ** //
/** The name of the database for WordPress */
define( 'DB_NAME', '_ask_onptp6ar0xi' );

/** Database username */
define( 'DB_USER', '_ask_onptp6ar0xi' );

/** Database password */
define( 'DB_PASSWORD', 'xeulncaxynj9adw' );

/** Database hostname */
define( 'DB_HOST', 'mysql322.phy.heteml.lan' );

/** Database charset to use in creating database tables. */
define( 'DB_CHARSET', 'utf8mb4' );

/** The database collate type. Don't change this if in doubt. */
define( 'DB_COLLATE', '' );

/**#@+
 * Authentication unique keys and salts.
 *
 * Change these to different unique phrases! You can generate these using
 * the {@link https://api.wordpress.org/secret-key/1.1/salt/ WordPress.org secret-key service}.
 *
 * You can change these at any point in time to invalidate all existing cookies.
 * This will force all users to have to log in again.
 *
 * @since 2.6.0
 */
define( 'AUTH_KEY',         '4cjXrkZxRwR==<-a069NUQF(9,hw$4:8XyVEZ;],!n|?4ItvFu}4Ah!Bsi=wdCu@' );
define( 'SECURE_AUTH_KEY',  '@GYuVu4XY]qSeaD%Kg8pE9-<i~$BfyV0_:ku9fIX1>,WtOb_:a%Sa;j}Pne;b?&0' );
define( 'LOGGED_IN_KEY',    'EqkDM.4DB&3;TUJi:N@od4).hl}}5E?~:3ha(c8Ih1Y[M!3bP/G/)O{p@Y);6{P-' );
define( 'NONCE_KEY',        '@=l|tjkQb}m*Afktt,71Y^gsvn8r%O2`feXPE|99al*4Hso@3l-S8rBuV~casUzN' );
define( 'AUTH_SALT',        '?M6Xo6YFig~+P)~JtL5r]{bra^HIs|0#owaTt>2Sz[bE~5s.Gn4d%WLeux(d:6f3' );
define( 'SECURE_AUTH_SALT', 't`MdOE;Daqm4mU)/}#qCY[9J*)(^$m<x#dQQ#fxdMZX>:eBMg.s`DtiM0pj4R0rT' );
define( 'LOGGED_IN_SALT',   'T|%V61>JRqbfL7..,5HNo,4ezdYHTF5)h9ce1v)Icj*)g@?r;b_3l>Ybw<$GW8N_' );
define( 'NONCE_SALT',       '8,2z69|YiFfFaz<pQLj]e|yQO11&0E~yO[oL[&$3Li~(XPv*4VAZw>+B,9G9Fkzy' );

/**#@-*/

/**
 * WordPress database table prefix.
 *
 * You can have multiple installations in one database if you give each
 * a unique prefix. Only numbers, letters, and underscores please!
 *
 * At the installation time, database tables are created with the specified prefix.
 * Changing this value after WordPress is installed will make your site think
 * it has not been installed.
 *
 * @link https://developer.wordpress.org/advanced-administration/wordpress/wp-config/#table-prefix
 */
$table_prefix = 'wp_';

/**
 * For developers: WordPress debugging mode.
 *
 * Change this to true to enable the display of notices during development.
 * It is strongly recommended that plugin and theme developers use WP_DEBUG
 * in their development environments.
 *
 * For information on other constants that can be used for debugging,
 * visit the documentation.
 *
 * @link https://developer.wordpress.org/advanced-administration/debug/debug-wordpress/
 */
define( 'WP_DEBUG', false );

/* Add any custom values between this line and the "stop editing" line. */

define('WP_HOME', 'http://ask11.jp/web/boat');
define('WP_SITEURL', 'http://ask11.jp/web/boat');


/* That's all, stop editing! Happy publishing. */



/** Absolute path to the WordPress directory. */
if ( ! defined( 'ABSPATH' ) ) {
	define( 'ABSPATH', __DIR__ . '/' );
}

/** Sets up WordPress vars and included files. */
require_once ABSPATH . 'wp-settings.php';

add_filter('xmlrpc_enabled', '__return_false');

add_filter('xmlrpc_methods', function($methods) {
    unset($methods['pingback.ping']);
    unset($methods['pingback.extensions.getPingbacks']);
    return $methods;
});
