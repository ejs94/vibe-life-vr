#include "common.h"
#include "xr_profile.h"
#include "xr_core.h"
#include "client.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <ctype.h>

#ifdef XASH_OPENXR

static vr_weapon_profile_t s_weaponProfiles[MAX_VR_WEAPON_PROFILES];
static int s_numWeaponProfiles = 0;
static qboolean s_profilesLoaded = false;

// Forward declarations of internal helpers
static void XR_RegisterDefaultWeaponProfiles( void );
static qboolean XR_ParseWeaponsJSON( const char *json_text, size_t length );

/*
====================
XR_ExtractModelBaseName

Extracts the filename part from a model path (e.g. "models/v_crowbar.mdl" -> "v_crowbar.mdl")
====================
*/
static const char *XR_ExtractModelBaseName( const char *path )
{
    if( !path || !*path )
        return "";

    const char *last_slash = strrchr( path, '/' );
    const char *last_bslash = strrchr( path, '\\' );
    const char *base = path;

    if( last_slash && last_slash >= base )
        base = last_slash + 1;
    if( last_bslash && last_bslash >= base )
        base = last_bslash + 1;

    return base;
}

/*
====================
XR_FindWeaponProfile

Searches profile table by full model path or base model name (case-insensitive)
====================
*/
const vr_weapon_profile_t *XR_FindWeaponProfile( const char *model_name )
{
    if( !model_name || !*model_name || s_numWeaponProfiles <= 0 )
        return NULL;

    const char *base = XR_ExtractModelBaseName( model_name );

    for( int i = 0; i < s_numWeaponProfiles; i++ )
    {
        if( !Q_stricmp( s_weaponProfiles[i].model_name, model_name ) ||
            !Q_stricmp( s_weaponProfiles[i].model_name, base ) )
        {
            return &s_weaponProfiles[i];
        }
    }

    return NULL;
}

/*
====================
XR_GetActiveWeaponProfile

Queries profile for currently held viewmodel in the engine
====================
*/
const vr_weapon_profile_t *XR_GetActiveWeaponProfile( void )
{
    if( clgame.viewent.model && clgame.viewent.model->name[0] )
    {
        return XR_FindWeaponProfile( clgame.viewent.model->name );
    }
    return NULL;
}

/*
====================
XR_GetWeaponProfileCount
====================
*/
int XR_GetWeaponProfileCount( void )
{
    return s_numWeaponProfiles;
}

/*
====================
XR_GetWeaponGripOffset
====================
*/
void XR_GetWeaponGripOffset( const char *model_name, vec3_t out_offset )
{
    if( !out_offset ) return;
    VectorClear( out_offset );

    const vr_weapon_profile_t *prof = XR_FindWeaponProfile( model_name );
    if( prof )
    {
        VectorCopy( prof->grip_offset, out_offset );
    }
}

/*
====================
XR_GetWeaponPitchAdjust
====================
*/
void XR_GetWeaponPitchAdjust( const char *model_name, float *out_pitch, float *out_yaw, float *out_roll )
{
    if( out_pitch ) *out_pitch = 0.0f;
    if( out_yaw )   *out_yaw   = 0.0f;
    if( out_roll )  *out_roll  = 0.0f;

    const vr_weapon_profile_t *prof = XR_FindWeaponProfile( model_name );
    if( prof )
    {
        if( out_pitch ) *out_pitch = prof->pitch_adjust;
        if( out_yaw )   *out_yaw   = prof->yaw_adjust;
        if( out_roll )  *out_roll  = prof->roll_adjust;
    }
}

/*
====================
XR_GetWeaponTwoHandParams
====================
*/
qboolean XR_GetWeaponTwoHandParams( const char *model_name, qboolean *out_twohanded, float *out_min_dist, float *out_max_dist )
{
    if( out_twohanded ) *out_twohanded = true;
    if( out_min_dist )  *out_min_dist  = 0.12f;
    if( out_max_dist )  *out_max_dist  = 0.55f;

    const vr_weapon_profile_t *prof = XR_FindWeaponProfile( model_name );
    if( prof )
    {
        if( out_twohanded ) *out_twohanded = prof->two_handed;
        if( out_min_dist )  *out_min_dist  = prof->two_hand_min_dist;
        if( out_max_dist )  *out_max_dist  = prof->two_hand_max_dist;
        return prof->two_handed;
    }
    return true;
}

/*
====================
XR_GetWeaponMuzzleParams
====================
*/
qboolean XR_GetWeaponMuzzleParams( const char *model_name, int *out_attachment, vec3_t out_fallback )
{
    if( out_attachment ) *out_attachment = 0;
    if( out_fallback )
    {
        out_fallback[0] = 0.0f;
        out_fallback[1] = 18.0f;
        out_fallback[2] = 0.0f;
    }

    const vr_weapon_profile_t *prof = XR_FindWeaponProfile( model_name );
    if( prof )
    {
        if( out_attachment ) *out_attachment = prof->muzzle_attachment;
        if( out_fallback )   VectorCopy( prof->muzzle_fallback, out_fallback );
        return (prof->muzzle_attachment >= 0);
    }
    return false;
}

/*
====================
XR_GetWeaponHaptics
====================
*/
qboolean XR_GetWeaponHaptics( const char *model_name, float *out_fire_amp, float *out_fire_dur )
{
    if( out_fire_amp ) *out_fire_amp = 0.8f;
    if( out_fire_dur ) *out_fire_dur = 60.0f;

    const vr_weapon_profile_t *prof = XR_FindWeaponProfile( model_name );
    if( prof && prof->haptic_fire_amplitude > 0.0f )
    {
        if( out_fire_amp ) *out_fire_amp = prof->haptic_fire_amplitude;
        if( out_fire_dur ) *out_fire_dur = prof->haptic_fire_duration_ms;
        return true;
    }
    return false;
}

// ==============================================================================
// Lightweight C JSON Parser for Declarative Weapon Profiles (vr_weapons.json)
// ==============================================================================

typedef struct
{
    const char *src;
    size_t      len;
    size_t      pos;
} json_parser_t;

static void JSON_SkipWhitespace( json_parser_t *p )
{
    while( p->pos < p->len )
    {
        char c = p->src[p->pos];
        if( isspace( (unsigned char)c ) )
        {
            p->pos++;
            continue;
        }
        // Line comment
        if( c == '/' && p->pos + 1 < p->len && p->src[p->pos + 1] == '/' )
        {
            p->pos += 2;
            while( p->pos < p->len && p->src[p->pos] != '\n' && p->src[p->pos] != '\r' )
                p->pos++;
            continue;
        }
        // Block comment
        if( c == '/' && p->pos + 1 < p->len && p->src[p->pos + 1] == '*' )
        {
            p->pos += 2;
            while( p->pos + 1 < p->len && !(p->src[p->pos] == '*' && p->src[p->pos + 1] == '/') )
                p->pos++;
            if( p->pos + 1 < p->len ) p->pos += 2;
            continue;
        }
        break;
    }
}

static char JSON_Peek( json_parser_t *p )
{
    JSON_SkipWhitespace( p );
    return (p->pos < p->len) ? p->src[p->pos] : '\0';
}

static char JSON_Get( json_parser_t *p )
{
    JSON_SkipWhitespace( p );
    return (p->pos < p->len) ? p->src[p->pos++] : '\0';
}

static qboolean JSON_ReadString( json_parser_t *p, char *out_buf, size_t max_len )
{
    JSON_SkipWhitespace( p );
    if( p->pos >= p->len || p->src[p->pos] != '\"' )
        return false;

    p->pos++; // skip opening quote
    size_t out_idx = 0;

    while( p->pos < p->len )
    {
        char c = p->src[p->pos++];
        if( c == '\"' )
        {
            if( out_buf && max_len > 0 )
                out_buf[out_idx < max_len ? out_idx : max_len - 1] = '\0';
            return true;
        }
        if( c == '\\' && p->pos < p->len )
        {
            c = p->src[p->pos++];
            if( c == 'n' ) c = '\n';
            else if( c == 't' ) c = '\t';
            else if( c == 'r' ) c = '\r';
        }
        if( out_buf && out_idx + 1 < max_len )
        {
            out_buf[out_idx++] = c;
        }
    }
    return false;
}

static qboolean JSON_ReadNumber( json_parser_t *p, float *out_val )
{
    JSON_SkipWhitespace( p );
    if( p->pos >= p->len ) return false;

    char num_buf[64];
    size_t idx = 0;

    while( p->pos < p->len && idx + 1 < sizeof(num_buf) )
    {
        char c = p->src[p->pos];
        if( isdigit((unsigned char)c) || c == '-' || c == '+' || c == '.' || c == 'e' || c == 'E' )
        {
            num_buf[idx++] = c;
            p->pos++;
        }
        else
        {
            break;
        }
    }
    num_buf[idx] = '\0';
    if( idx == 0 ) return false;

    if( out_val )
        *out_val = (float)atof( num_buf );
    return true;
}

static qboolean JSON_ReadBool( json_parser_t *p, qboolean *out_val )
{
    JSON_SkipWhitespace( p );
    if( p->pos + 4 <= p->len && !strncmp( &p->src[p->pos], "true", 4 ) )
    {
        p->pos += 4;
        if( out_val ) *out_val = true;
        return true;
    }
    if( p->pos + 5 <= p->len && !strncmp( &p->src[p->pos], "false", 5 ) )
    {
        p->pos += 5;
        if( out_val ) *out_val = false;
        return true;
    }
    return false;
}

static void JSON_SkipValue( json_parser_t *p );

static void JSON_SkipObject( json_parser_t *p )
{
    if( JSON_Get( p ) != '{' ) return;
    int depth = 1;
    while( p->pos < p->len && depth > 0 )
    {
        char c = p->src[p->pos++];
        if( c == '{' ) depth++;
        else if( c == '}' ) depth--;
        else if( c == '\"' )
        {
            p->pos--;
            JSON_ReadString( p, NULL, 0 );
        }
    }
}

static void JSON_SkipArray( json_parser_t *p )
{
    if( JSON_Get( p ) != '[' ) return;
    int depth = 1;
    while( p->pos < p->len && depth > 0 )
    {
        char c = p->src[p->pos++];
        if( c == '[' ) depth++;
        else if( c == ']' ) depth--;
        else if( c == '\"' )
        {
            p->pos--;
            JSON_ReadString( p, NULL, 0 );
        }
    }
}

static void JSON_SkipValue( json_parser_t *p )
{
    char c = JSON_Peek( p );
    if( c == '{' )
        JSON_SkipObject( p );
    else if( c == '[' )
        JSON_SkipArray( p );
    else if( c == '\"' )
        JSON_ReadString( p, NULL, 0 );
    else
    {
        // Skip until comma, closing brace, or bracket
        while( p->pos < p->len )
        {
            char ch = p->src[p->pos];
            if( ch == ',' || ch == '}' || ch == ']' || isspace((unsigned char)ch) )
                break;
            p->pos++;
        }
    }
}

static qboolean JSON_ReadFloatArray3( json_parser_t *p, vec3_t out_vec )
{
    JSON_SkipWhitespace( p );
    if( JSON_Get( p ) != '[' ) return false;

    VectorClear( out_vec );
    for( int i = 0; i < 3; i++ )
    {
        JSON_SkipWhitespace( p );
        float val = 0.0f;
        if( !JSON_ReadNumber( p, &val ) )
            break;
        out_vec[i] = val;
        JSON_SkipWhitespace( p );
        if( JSON_Peek( p ) == ',' )
            JSON_Get( p );
    }

    JSON_SkipWhitespace( p );
    if( JSON_Peek( p ) == ']' )
        JSON_Get( p );

    return true;
}

/*
====================
XR_ParseWeaponsJSON

Parses declarative JSON weapon profiles into the profile cache table
====================
*/
static qboolean XR_ParseWeaponsJSON( const char *json_text, size_t length )
{
    if( !json_text || length == 0 )
        return false;

    json_parser_t p = { json_text, length, 0 };
    if( JSON_Get( &p ) != '{' )
        return false;

    while( JSON_Peek( &p ) != '}' && p.pos < p.len )
    {
        char key[64];
        if( !JSON_ReadString( &p, key, sizeof(key) ) )
            break;

        if( JSON_Get( &p ) != ':' )
            break;

        if( !Q_strcmp( key, "weapons" ) )
        {
            if( JSON_Get( &p ) != '{' )
                break;

            while( JSON_Peek( &p ) != '}' && p.pos < p.len )
            {
                char weapon_key[64];
                if( !JSON_ReadString( &p, weapon_key, sizeof(weapon_key) ) )
                    break;

                if( JSON_Get( &p ) != ':' )
                    break;

                if( JSON_Get( &p ) != '{' )
                {
                    JSON_SkipValue( &p );
                    continue;
                }

                if( s_numWeaponProfiles < MAX_VR_WEAPON_PROFILES )
                {
                    vr_weapon_profile_t *wp = &s_weaponProfiles[s_numWeaponProfiles];
                    memset( wp, 0, sizeof(*wp) );
                    Q_strncpy( wp->model_name, weapon_key, sizeof(wp->model_name) );
                    wp->muzzle_attachment = 0;
                    wp->ejection_attachment = -1;
                    wp->magwell_attachment = -1;
                    wp->two_handed = true;
                    wp->two_hand_min_dist = 0.12f;
                    wp->two_hand_max_dist = 0.55f;
                    wp->haptic_fire_amplitude = 0.8f;
                    wp->haptic_fire_duration_ms = 60.0f;

                    while( JSON_Peek( &p ) != '}' && p.pos < p.len )
                    {
                        char prop[64];
                        if( !JSON_ReadString( &p, prop, sizeof(prop) ) )
                            break;
                        if( JSON_Get( &p ) != ':' )
                            break;

                        if( !Q_strcmp( prop, "name" ) )
                        {
                            JSON_ReadString( &p, wp->display_name, sizeof(wp->display_name) );
                        }
                        else if( !Q_strcmp( prop, "type" ) )
                        {
                            JSON_ReadString( &p, wp->type, sizeof(wp->type) );
                        }
                        else if( !Q_strcmp( prop, "muzzle_attachment" ) )
                        {
                            float val = 0.0f;
                            JSON_ReadNumber( &p, &val );
                            wp->muzzle_attachment = (int)val;
                        }
                        else if( !Q_strcmp( prop, "muzzle_offset_fallback" ) )
                        {
                            JSON_ReadFloatArray3( &p, wp->muzzle_fallback );
                        }
                        else if( !Q_strcmp( prop, "ejection_attachment" ) )
                        {
                            float val = -1.0f;
                            JSON_ReadNumber( &p, &val );
                            wp->ejection_attachment = (int)val;
                        }
                        else if( !Q_strcmp( prop, "magwell_attachment" ) )
                        {
                            float val = -1.0f;
                            JSON_ReadNumber( &p, &val );
                            wp->magwell_attachment = (int)val;
                        }
                        else if( !Q_strcmp( prop, "grip_offset" ) )
                        {
                            JSON_ReadFloatArray3( &p, wp->grip_offset );
                        }
                        else if( !Q_strcmp( prop, "pitch_adjust" ) )
                        {
                            JSON_ReadNumber( &p, &wp->pitch_adjust );
                        }
                        else if( !Q_strcmp( prop, "yaw_adjust" ) )
                        {
                            JSON_ReadNumber( &p, &wp->yaw_adjust );
                        }
                        else if( !Q_strcmp( prop, "roll_adjust" ) )
                        {
                            JSON_ReadNumber( &p, &wp->roll_adjust );
                        }
                        else if( !Q_strcmp( prop, "two_handed" ) )
                        {
                            JSON_ReadBool( &p, &wp->two_handed );
                        }
                        else if( !Q_strcmp( prop, "two_hand_min_dist" ) )
                        {
                            JSON_ReadNumber( &p, &wp->two_hand_min_dist );
                        }
                        else if( !Q_strcmp( prop, "two_hand_max_dist" ) )
                        {
                            JSON_ReadNumber( &p, &wp->two_hand_max_dist );
                        }
                        else if( !Q_strcmp( prop, "recoil_pitch" ) )
                        {
                            JSON_ReadNumber( &p, &wp->recoil_pitch );
                        }
                        else if( !Q_strcmp( prop, "haptics" ) )
                        {
                            if( JSON_Get( &p ) == '{' )
                            {
                                while( JSON_Peek( &p ) != '}' && p.pos < p.len )
                                {
                                    char hprop[64];
                                    if( !JSON_ReadString( &p, hprop, sizeof(hprop) ) ) break;
                                    if( JSON_Get( &p ) != ':' ) break;
                                    if( !Q_strcmp( hprop, "fire_amplitude" ) )
                                        JSON_ReadNumber( &p, &wp->haptic_fire_amplitude );
                                    else if( !Q_strcmp( hprop, "fire_duration_ms" ) )
                                        JSON_ReadNumber( &p, &wp->haptic_fire_duration_ms );
                                    else if( !Q_strcmp( hprop, "impact_amplitude" ) )
                                        JSON_ReadNumber( &p, &wp->haptic_impact_amplitude );
                                    else if( !Q_strcmp( hprop, "impact_duration_ms" ) )
                                        JSON_ReadNumber( &p, &wp->haptic_impact_duration_ms );
                                    else
                                        JSON_SkipValue( &p );

                                    if( JSON_Peek( &p ) == ',' ) JSON_Get( &p );
                                }
                                if( JSON_Peek( &p ) == '}' ) JSON_Get( &p );
                            }
                        }
                        else
                        {
                            JSON_SkipValue( &p );
                        }

                        if( JSON_Peek( &p ) == ',' )
                            JSON_Get( &p );
                    }

                    if( JSON_Peek( &p ) == '}' )
                        JSON_Get( &p );

                    s_numWeaponProfiles++;
                }
                else
                {
                    JSON_SkipValue( &p );
                }

                if( JSON_Peek( &p ) == ',' )
                    JSON_Get( &p );
            }

            if( JSON_Peek( &p ) == '}' )
                JSON_Get( &p );
        }
        else
        {
            JSON_SkipValue( &p );
        }

        if( JSON_Peek( &p ) == ',' )
            JSON_Get( &p );
    }

    return (s_numWeaponProfiles > 0);
}

/*
====================
XR_RegisterDefaultWeaponProfiles

Built-in hardcoded fallback calibration for standard Half-Life arsenal
====================
*/
static void XR_RegisterDefaultWeaponProfiles( void )
{
    // Crowbar
    vr_weapon_profile_t *w = &s_weaponProfiles[s_numWeaponProfiles++];
    memset( w, 0, sizeof(*w) );
    Q_strncpy( w->model_name, "v_crowbar.mdl", sizeof(w->model_name) );
    Q_strncpy( w->display_name, "Crowbar", sizeof(w->display_name) );
    Q_strncpy( w->type, "melee", sizeof(w->type) );
    w->muzzle_attachment = -1;
    w->grip_offset[1] = 3.0f; w->grip_offset[2] = -1.0f;
    w->pitch_adjust = -12.0f;
    w->two_handed = false;
    w->haptic_impact_amplitude = 1.0f;
    w->haptic_impact_duration_ms = 120.0f;

    // Glock 17
    w = &s_weaponProfiles[s_numWeaponProfiles++];
    memset( w, 0, sizeof(*w) );
    Q_strncpy( w->model_name, "v_9mmhandgun.mdl", sizeof(w->model_name) );
    Q_strncpy( w->display_name, "Glock 17 (9mm Handgun)", sizeof(w->display_name) );
    Q_strncpy( w->type, "hitscan", sizeof(w->type) );
    w->muzzle_attachment = 0;
    w->muzzle_fallback[1] = 11.5f; w->muzzle_fallback[2] = 2.2f;
    w->pitch_adjust = -5.0f;
    w->two_handed = true;
    w->two_hand_min_dist = 0.12f; w->two_hand_max_dist = 0.45f;
    w->haptic_fire_amplitude = 0.85f; w->haptic_fire_duration_ms = 65.0f;

    // Python .357
    w = &s_weaponProfiles[s_numWeaponProfiles++];
    memset( w, 0, sizeof(*w) );
    Q_strncpy( w->model_name, "v_357.mdl", sizeof(w->model_name) );
    Q_strncpy( w->display_name, "Colt Python .357 Magnum", sizeof(w->display_name) );
    Q_strncpy( w->type, "hitscan", sizeof(w->type) );
    w->muzzle_attachment = 0;
    w->muzzle_fallback[1] = 13.0f; w->muzzle_fallback[2] = 2.8f;
    w->pitch_adjust = -5.0f;
    w->two_handed = true;
    w->two_hand_min_dist = 0.12f; w->two_hand_max_dist = 0.45f;
    w->haptic_fire_amplitude = 1.0f; w->haptic_fire_duration_ms = 100.0f;

    // MP5 / 9mmAR
    w = &s_weaponProfiles[s_numWeaponProfiles++];
    memset( w, 0, sizeof(*w) );
    Q_strncpy( w->model_name, "v_9mmar.mdl", sizeof(w->model_name) );
    Q_strncpy( w->display_name, "MP5 / 9mm Assault Rifle", sizeof(w->display_name) );
    Q_strncpy( w->type, "hitscan", sizeof(w->type) );
    w->muzzle_attachment = 0;
    w->muzzle_fallback[1] = 18.0f; w->muzzle_fallback[2] = 1.8f;
    w->pitch_adjust = -4.0f;
    w->two_handed = true;
    w->two_hand_min_dist = 0.18f; w->two_hand_max_dist = 0.55f;
    w->haptic_fire_amplitude = 0.70f; w->haptic_fire_duration_ms = 45.0f;

    // SPAS-12 Shotgun
    w = &s_weaponProfiles[s_numWeaponProfiles++];
    memset( w, 0, sizeof(*w) );
    Q_strncpy( w->model_name, "v_shotgun.mdl", sizeof(w->model_name) );
    Q_strncpy( w->display_name, "SPAS-12 Combat Shotgun", sizeof(w->display_name) );
    Q_strncpy( w->type, "hitscan", sizeof(w->type) );
    w->muzzle_attachment = 0;
    w->muzzle_fallback[1] = 21.0f; w->muzzle_fallback[2] = 2.0f;
    w->pitch_adjust = -4.0f;
    w->two_handed = true;
    w->two_hand_min_dist = 0.22f; w->two_hand_max_dist = 0.60f;
    w->haptic_fire_amplitude = 1.0f; w->haptic_fire_duration_ms = 110.0f;

    // Crossbow
    w = &s_weaponProfiles[s_numWeaponProfiles++];
    memset( w, 0, sizeof(*w) );
    Q_strncpy( w->model_name, "v_crossbow.mdl", sizeof(w->model_name) );
    Q_strncpy( w->display_name, "Crossbow", sizeof(w->display_name) );
    Q_strncpy( w->type, "projectile", sizeof(w->type) );
    w->muzzle_attachment = 0;
    w->muzzle_fallback[1] = 22.0f; w->muzzle_fallback[2] = 1.5f;
    w->pitch_adjust = -3.0f;
    w->two_handed = true;
    w->two_hand_min_dist = 0.20f; w->two_hand_max_dist = 0.55f;

    // RPG
    w = &s_weaponProfiles[s_numWeaponProfiles++];
    memset( w, 0, sizeof(*w) );
    Q_strncpy( w->model_name, "v_rpg.mdl", sizeof(w->model_name) );
    Q_strncpy( w->display_name, "RPG Launcher", sizeof(w->display_name) );
    Q_strncpy( w->type, "projectile", sizeof(w->type) );
    w->muzzle_attachment = 0;
    w->muzzle_fallback[1] = 26.0f; w->muzzle_fallback[2] = 3.0f;
    w->pitch_adjust = 0.0f;
    w->two_handed = true;
    w->two_hand_min_dist = 0.25f; w->two_hand_max_dist = 0.65f;

    // Gauss / Tau Cannon
    w = &s_weaponProfiles[s_numWeaponProfiles++];
    memset( w, 0, sizeof(*w) );
    Q_strncpy( w->model_name, "v_gauss.mdl", sizeof(w->model_name) );
    Q_strncpy( w->display_name, "Tau Cannon / Gauss Gun", sizeof(w->display_name) );
    Q_strncpy( w->type, "beam", sizeof(w->type) );
    w->muzzle_attachment = 0;
    w->muzzle_fallback[1] = 20.0f; w->muzzle_fallback[2] = 1.0f;
    w->pitch_adjust = -2.0f;
    w->two_handed = true;
    w->two_hand_min_dist = 0.20f; w->two_hand_max_dist = 0.55f;

    // Egon / Gluon Gun
    w = &s_weaponProfiles[s_numWeaponProfiles++];
    memset( w, 0, sizeof(*w) );
    Q_strncpy( w->model_name, "v_egon.mdl", sizeof(w->model_name) );
    Q_strncpy( w->display_name, "Gluon Gun / Egon", sizeof(w->display_name) );
    Q_strncpy( w->type, "beam", sizeof(w->type) );
    w->muzzle_attachment = 0;
    w->muzzle_fallback[1] = 22.0f; w->muzzle_fallback[2] = 2.0f;
    w->pitch_adjust = -2.0f;
    w->two_handed = true;
    w->two_hand_min_dist = 0.22f; w->two_hand_max_dist = 0.55f;

    // Hornet Gun / Hivehand
    w = &s_weaponProfiles[s_numWeaponProfiles++];
    memset( w, 0, sizeof(*w) );
    Q_strncpy( w->model_name, "v_hgun.mdl", sizeof(w->model_name) );
    Q_strncpy( w->display_name, "Hornet Gun / Hivehand", sizeof(w->display_name) );
    Q_strncpy( w->type, "projectile", sizeof(w->type) );
    w->muzzle_attachment = 0;
    w->muzzle_fallback[1] = 15.0f; w->muzzle_fallback[2] = 0.5f;
    w->pitch_adjust = -6.0f;
    w->two_handed = false;

    // Hand Grenade
    w = &s_weaponProfiles[s_numWeaponProfiles++];
    memset( w, 0, sizeof(*w) );
    Q_strncpy( w->model_name, "v_grenade.mdl", sizeof(w->model_name) );
    Q_strncpy( w->display_name, "Hand Grenade", sizeof(w->display_name) );
    Q_strncpy( w->type, "toss", sizeof(w->type) );
    w->muzzle_attachment = -1;
    w->two_handed = false;

    // Tripmine
    w = &s_weaponProfiles[s_numWeaponProfiles++];
    memset( w, 0, sizeof(*w) );
    Q_strncpy( w->model_name, "v_tripmine.mdl", sizeof(w->model_name) );
    Q_strncpy( w->display_name, "Laser Tripmine", sizeof(w->display_name) );
    Q_strncpy( w->type, "placeable", sizeof(w->type) );
    w->muzzle_attachment = 0;
    w->muzzle_fallback[1] = 8.0f; w->muzzle_fallback[2] = 1.0f;
    w->two_handed = false;

    // Satchel Charge
    w = &s_weaponProfiles[s_numWeaponProfiles++];
    memset( w, 0, sizeof(*w) );
    Q_strncpy( w->model_name, "v_satchel.mdl", sizeof(w->model_name) );
    Q_strncpy( w->display_name, "Satchel Charge", sizeof(w->display_name) );
    Q_strncpy( w->type, "toss", sizeof(w->type) );
    w->muzzle_attachment = -1;
    w->two_handed = false;

    // Satchel Radio Detonator
    w = &s_weaponProfiles[s_numWeaponProfiles++];
    memset( w, 0, sizeof(*w) );
    Q_strncpy( w->model_name, "v_satchel_radio.mdl", sizeof(w->model_name) );
    Q_strncpy( w->display_name, "Satchel Detonator", sizeof(w->display_name) );
    Q_strncpy( w->type, "tool", sizeof(w->type) );
    w->muzzle_attachment = -1;
    w->two_handed = false;

    // Snark
    w = &s_weaponProfiles[s_numWeaponProfiles++];
    memset( w, 0, sizeof(*w) );
    Q_strncpy( w->model_name, "v_squeak.mdl", sizeof(w->model_name) );
    Q_strncpy( w->display_name, "Snark", sizeof(w->display_name) );
    Q_strncpy( w->type, "toss", sizeof(w->type) );
    w->muzzle_attachment = -1;
    w->two_handed = false;

    // Standalone Hand presence
    w = &s_weaponProfiles[s_numWeaponProfiles++];
    memset( w, 0, sizeof(*w) );
    Q_strncpy( w->model_name, "v_hand.mdl", sizeof(w->model_name) );
    Q_strncpy( w->display_name, "VR Hand Presence", sizeof(w->display_name) );
    Q_strncpy( w->type, "hand", sizeof(w->type) );
    w->muzzle_attachment = -1;
    w->two_handed = false;
}

/*
====================
XR_ReloadWeaponProfiles

Scans for vr_weapons.json and parses custom calibration manifest
====================
*/
void XR_ReloadWeaponProfiles( void )
{
    s_numWeaponProfiles = 0;

    const char *paths[] = {
        va( "%s_vr/models/vr_weapons.json", FS_Gamedir() ),
        va( "%s/models/vr_weapons.json", FS_Gamedir() ),
        "valve_vr/models/vr_weapons.json",
        "models/vr_weapons.json",
        NULL
    };

    byte *file_buffer = NULL;
    fs_offset_t file_len = 0;
    const char *loaded_path = NULL;

    for( int i = 0; paths[i]; i++ )
    {
        file_buffer = FS_LoadFile( paths[i], &file_len, false );
        if( file_buffer && file_len > 0 )
        {
            loaded_path = paths[i];
            break;
        }
    }

    if( file_buffer && file_len > 0 )
    {
        qboolean success = XR_ParseWeaponsJSON( (const char *)file_buffer, (size_t)file_len );
        Mem_Free( file_buffer );

        if( success )
        {
            Con_Printf( "^2[VR_WEAPON_PROFILES] Successfully loaded %d weapon profiles from '%s'\n",
                s_numWeaponProfiles, loaded_path );
            s_profilesLoaded = true;
            return;
        }
        else
        {
            Con_Printf( "^1[VR_WEAPON_PROFILES] Parse error in '%s', falling back to defaults\n", loaded_path );
        }
    }

    // Fallback to compiled-in reference calibration
    XR_RegisterDefaultWeaponProfiles();
    Con_Printf( "^3[VR_WEAPON_PROFILES] Loaded %d reference built-in weapon profiles\n", s_numWeaponProfiles );
    s_profilesLoaded = true;
}

/*
====================
XR_ReloadWeaponProfiles_f

Console command handler
====================
*/
static void XR_ReloadWeaponProfiles_f( void )
{
    XR_ReloadWeaponProfiles();
}

/*
====================
XR_DumpWeaponProfile_f

Dumps the current weapon calibration parameters as a copy-pasteable JSON block
====================
*/
static void XR_DumpWeaponProfile_f( void )
{
    const vr_weapon_profile_t *prof = XR_GetActiveWeaponProfile();
    const char *model_name = (prof && prof->model_name[0]) ? prof->model_name : "models/v_weapon.mdl";
    const char *display_name = (prof && prof->display_name[0]) ? prof->display_name : "Calibrated Weapon";

    float fwd = vr_weapon_offset_forward ? vr_weapon_offset_forward->value : 0.0f;
    float rt  = vr_weapon_offset_right ? vr_weapon_offset_right->value : 0.0f;
    float up  = vr_weapon_offset_up ? vr_weapon_offset_up->value : 0.0f;

    if( prof )
    {
        fwd += prof->grip_offset[0];
        rt  += prof->grip_offset[1];
        up  += prof->grip_offset[2];
    }

    float pitch = vr_weapon_pitchadjust ? vr_weapon_pitchadjust->value : 0.0f;
    float yaw   = vr_weapon_yawadjust ? vr_weapon_yawadjust->value : 0.0f;
    float roll  = vr_weapon_rolladjust ? vr_weapon_rolladjust->value : 0.0f;

    if( prof )
    {
        pitch += prof->pitch_adjust;
        yaw   += prof->yaw_adjust;
        roll  += prof->roll_adjust;
    }

    Con_Printf( "^2=== VR WEAPON 6DOF CALIBRATION PROFILE ===\n" );
    Con_Printf( "Model: ^3%s^7 (%s)\n", model_name, display_name );
    Con_Printf( "Grip Offset: [ forward=%.2f, right=%.2f, up=%.2f ] (GoldSrc units)\n", fwd, rt, up );
    Con_Printf( "Angles Adjust: pitch=%.2f, yaw=%.2f, roll=%.2f degrees\n\n", pitch, yaw, roll );
    Con_Printf( "^2JSON block for vr_weapons.json:\n" );
    Con_Printf( "{\n" );
    Con_Printf( "  \"model\": \"%s\",\n", model_name );
    Con_Printf( "  \"display_name\": \"%s\",\n", display_name );
    Con_Printf( "  \"grip_offset\": [ %.2f, %.2f, %.2f ],\n", fwd, rt, up );
    Con_Printf( "  \"pitch_adjust\": %.2f,\n", pitch );
    Con_Printf( "  \"yaw_adjust\": %.2f,\n", yaw );
    Con_Printf( "  \"roll_adjust\": %.2f\n", roll );
    Con_Printf( "}\n" );
    Con_Printf( "^2============================================\n" );
}

/*
====================
XR_InitWeaponProfiles

Initializes weapon profiles system and registers console command
====================
*/
void XR_InitWeaponProfiles( void )
{
    if( !s_profilesLoaded )
    {
        Cmd_AddCommand( "vr_reload_weapon_profiles", XR_ReloadWeaponProfiles_f, "Reload vr_weapons.json declarative calibration profiles" );
        Cmd_AddCommand( "vr_dump_weapon_profile", XR_DumpWeaponProfile_f, "Dump active weapon 6DOF calibration as JSON for vr_weapons.json" );
        XR_ReloadWeaponProfiles();
    }
}

#endif // XASH_OPENXR
