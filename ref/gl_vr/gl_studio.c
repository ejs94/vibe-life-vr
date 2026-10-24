/*
gl_studio.c - studio model renderer
Copyright (C) 2010 Uncle Mike

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
*/

#include "gl_local.h"
#include "xr_core.h"
#include "xr_input.h"
#include "xr_profile.h"
#include "xash3d_mathlib.h"
#include "const.h"
#include "r_studioint.h"
#include "triangleapi.h"
#include "studio.h"
#include "pm_local.h"

#define EVENT_CLIENT	5000	// less than this value it's a server-side studio events
#define MAX_LOCALLIGHTS	4

typedef struct
{
	char		name[MAX_OSPATH];
	char		modelname[MAX_OSPATH];
	model_t		*model;
} player_model_t;

// never gonna change, just shut up const warning
CVAR_DEFINE_AUTO( r_shadows, "0", 0, "draw ugly shadows" );

#ifdef XASH_OPENXR
static cl_entity_t s_offhandEnt;
static cl_entity_t s_primaryHandEnt;
static model_t     *s_handModel = NULL;
static model_t     *s_primaryHandModelOverride = NULL;
static char         s_primaryHandModelName[64] = "";
static qboolean    s_viewmodel_has_offhand = false;
static qboolean    s_twohanded_active = false;
static vec3_t      s_vrDebugRawHandOrigin = {0};
static vec3_t      s_vrDebugRawHandAngles = {0};
static qboolean    s_vrDebugHandActive = false;
static vec3_t      s_vrDebugOffHandOrigin = {0};
static vec3_t      s_vrDebugOffHandAngles = {0};
static qboolean    s_vrDebugOffHandActive = false;
static vec3_t      s_vrDebugWeaponCOM = {0};
static int         s_vrDebugNumHitboxes = 0;
static vec3_t      s_vrDebugMuzzlePos = {0};
static char        s_vrDebugWeaponModelName[64] = {0};
static void R_VR_DebugGripBone( cl_entity_t *ent, model_t *model );
#endif

static const vec3_t hullcolor[8] =
{
{ 1.0f, 1.0f, 1.0f },
{ 1.0f, 0.5f, 0.5f },
{ 0.5f, 1.0f, 0.5f },
{ 1.0f, 1.0f, 0.5f },
{ 0.5f, 0.5f, 1.0f },
{ 1.0f, 0.5f, 1.0f },
{ 0.5f, 1.0f, 1.0f },
{ 1.0f, 1.0f, 1.0f },
};

typedef struct sortedmesh_s
{
	mstudiomesh_t	*mesh;
	int		flags;			// face flags
} sortedmesh_t;

typedef struct
{
	double		time;
	double		frametime;
	int		framecount;		// studio framecount
	qboolean		interpolate;
	int		rendermode;
	float		blend;			// blend value

	// bones
	matrix3x4		rotationmatrix;
	matrix3x4		bonestransform[MAXSTUDIOBONES];
	matrix3x4		lighttransform[MAXSTUDIOBONES];

	// boneweighting stuff
	matrix3x4		worldtransform[MAXSTUDIOBONES];

	// cached bones
	matrix3x4		cached_bonestransform[MAXSTUDIOBONES];
	matrix3x4		cached_lighttransform[MAXSTUDIOBONES];
	char		cached_bonenames[MAXSTUDIOBONES][32];
	int		cached_numbones;		// number of bones in cache

	sortedmesh_t	meshes[MAXSTUDIOMESHES];	// sorted meshes
	vec3_t		verts[MAXSTUDIOVERTS];
	vec3_t		norms[MAXSTUDIOVERTS];

	// lighting state
	float		ambientlight;
	float		shadelight;
	vec3_t		lightvec;			// averaging light direction
	vec3_t		lightspot;		// shadow spot
	vec3_t		lightcolor;		// averaging lightcolor
	vec3_t		blightvec[MAXSTUDIOBONES];	// bone light vecs
	vec3_t		lightvalues[MAXSTUDIOVERTS];	// precomputed lightvalues per each shared vertex of submodel

	// chrome stuff
	vec3_t		chrome_origin;
	vec2_t		chrome[MAXSTUDIOVERTS];	// texture coords for surface normals
	vec3_t		chromeright[MAXSTUDIOBONES];	// chrome vector "right" in bone reference frames
	vec3_t		chromeup[MAXSTUDIOBONES];	// chrome vector "up" in bone reference frames
	int		chromeage[MAXSTUDIOBONES];	// last time chrome vectors were updated

	// glowshell stuff
	int		normaltable[MAXSTUDIOVERTS];	// glowshell uses this

	// elights cache
	int		numlocallights;
	int		lightage[MAXSTUDIOBONES];
	dlight_t		*locallight[MAX_LOCALLIGHTS];
	int		locallightcolor[MAX_LOCALLIGHTS][3];
	vec4_t		lightpos[MAXSTUDIOVERTS][MAX_LOCALLIGHTS];
	vec3_t		lightbonepos[MAXSTUDIOBONES][MAX_LOCALLIGHTS];
	float		locallightR2[MAX_LOCALLIGHTS];

	// playermodels
	player_model_t  player_models[MAX_CLIENTS];

	// drawelements renderer
	vec3_t			arrayverts[MAXSTUDIOVERTS];
	vec2_t			arraycoord[MAXSTUDIOVERTS];
	unsigned short	arrayelems[MAXSTUDIOVERTS*6];
	GLubyte			arraycolor[MAXSTUDIOVERTS][4];
	uint			numverts;
	uint			numelems;
} studio_draw_state_t;

// studio-related cvars
CVAR_DEFINE_AUTO( r_studio_sort_textures, "0", FCVAR_GLCONFIG, "change draw order for additive meshes" );
CVAR_DEFINE_AUTO( r_studio_drawelements, "1", FCVAR_GLCONFIG, "use glDrawElements for studiomodels" );
CVAR_DEFINE_AUTO( r_studio_builtin_renderer, "0", 0, "use built-in studio model renderer instead of the one provided by client library (debugging)" );
static cvar_t			*cl_righthand = NULL;

static r_studio_interface_t	*pStudioDraw;
static studio_draw_state_t	g_studio;		// global studio state

// global variables
static qboolean m_fDoRemap;
static mstudiomodel_t *m_pSubModel;
static mstudiobodyparts_t *m_pBodyPart;
static player_info_t *m_pPlayerInfo;
static studiohdr_t *m_pStudioHeader;
static float m_flGaitMovement;
static int g_nTopColor, g_nBottomColor;	// remap colors
static int g_nFaceFlags, g_nForceFaceFlags;

/*
====================
R_StudioInit

====================
*/
void R_StudioInit( void )
{

#if XASH_PSVITA
	// don't do the same array-building work twice since that's what our FFP shim does anyway
	gEngfuncs.Cvar_FullSet( "r_studio_drawelements", "0", FCVAR_READ_ONLY );
#endif

	Matrix3x4_LoadIdentity( g_studio.rotationmatrix );

	g_studio.interpolate = true;
	g_studio.framecount = 0;
	m_fDoRemap = false;
}

/*
================
R_StudioSetupTimings

init current time for a given model
================
*/
static void R_StudioSetupTimings( void )
{
	if( FBitSet( RI.rvp.flags, RF_DRAW_WORLD ))
	{
		// synchronize with server time
		g_studio.time = gp_cl->time;
		g_studio.frametime = gp_cl->time - gp_cl->oldtime;
	}
	else
	{
		// menu stuff
		g_studio.time = gp_host->realtime;
		g_studio.frametime = gp_host->frametime;
	}
}

/*
====================
R_VR_PrimaryHandIndex / R_VR_SecondaryHandIndex

Resolve which physical controller drives the weapon hand and which one drives
the free hand.
====================
*/
static int R_VR_PrimaryHandIndex( void )
{
	return ( vr_lefthanded && vr_lefthanded->value > 0.0f ) ? VR_HAND_LEFT : VR_HAND_RIGHT;
}

static int R_VR_SecondaryHandIndex( void )
{
	return ( vr_lefthanded && vr_lefthanded->value > 0.0f ) ? VR_HAND_RIGHT : VR_HAND_LEFT;
}

/*
====================
R_VR_WeaponTrueDepth

In VR the viewmodel lives in world space, so walls must be allowed to occlude
it. Flat-screen GoldSrc compresses the viewmodel depth range to keep it in front
of the world; that behaviour is only used when this cvar is disabled.
====================
*/
static qboolean R_VR_WeaponTrueDepth( void )
{
	static cvar_t *vr_weapon_true_depth = NULL;
	if( !vr_weapon_true_depth ) vr_weapon_true_depth = gEngfuncs.pfnGetCvarPointer( "vr_weapon_true_depth" );
	return ( vr_weapon_true_depth && vr_weapon_true_depth->value > 0.0f );
}

/*
====================
R_HandEntityNeedsMirror

models/v_hand.mdl contains an anatomical right chain and an anatomical left
chain. Each hand entity selects the chain matching its controller (see
R_DrawHandEntity), so the model is never reflected: a reflection would also
invert the procedural finger curl direction.
====================
*/
static qboolean R_HandEntityNeedsMirror( const cl_entity_t *e )
{
	(void)e;
	return false;
}

/*
====================
R_VR_OffHandAttachedToWeapon

True when the secondary hand is gripping the weapon two-handed. In that case
the viewmodel already contains the off-hand and the standalone hand must stay
hidden to avoid a duplicated third hand.
====================
*/
static qboolean R_VR_OffHandAttachedToWeapon( void )
{
	if( XR_IsTwoHandStabilized( ))
		return true;

	static cvar_t *vr_twohanded = NULL;
	if( !vr_twohanded ) vr_twohanded = gEngfuncs.pfnGetCvarPointer( "vr_twohanded" );
	if( !vr_twohanded || vr_twohanded->value <= 0.0f )
		return false;

	float trigSec = 0.0f, gripSec = 0.0f, thmbSec = 0.0f;
	XR_GetFingerCurlAxes( R_VR_SecondaryHandIndex(), &trigSec, &gripSec, &thmbSec );
	return ( gripSec > 0.4f );
}

/*
====================
R_LoadVrHandModel

Loads the standalone hand presence model, with an optional override for the
empty primary hand.
====================
*/
static model_t *R_LoadVrHandModel( qboolean primary )
{
	if( primary )
	{
		static cvar_t *vr_primary_hand_model = NULL;
		if( !vr_primary_hand_model ) vr_primary_hand_model = gEngfuncs.pfnGetCvarPointer( "vr_primary_hand_model" );

		if( vr_primary_hand_model && vr_primary_hand_model->string[0] )
		{
			// Reload when the user points the cvar at a different model
			if( Q_strcmp( s_primaryHandModelName, vr_primary_hand_model->string ))
			{
				Q_strncpy( s_primaryHandModelName, vr_primary_hand_model->string, sizeof( s_primaryHandModelName ));
				s_primaryHandModelOverride = gEngfuncs.Mod_ForName( vr_primary_hand_model->string, false, true );
			}

			if( s_primaryHandModelOverride && s_primaryHandModelOverride->type == mod_studio )
				return s_primaryHandModelOverride;
		}
	}

	if( !s_handModel )
	{
		s_handModel = gEngfuncs.Mod_ForName( "models/v_hand.mdl", false, true );
		if( !s_handModel )
			s_handModel = gEngfuncs.Mod_ForName( "models/v_hands.mdl", false, true );
		if( !s_handModel )
			s_handModel = gEngfuncs.Mod_ForName( "models/v_vhand.mdl", false, true );
	}

	return s_handModel;
}

/*
================
R_AllowFlipViewModel

should a flip the viewmodel if cl_righthand is set to 1
================
*/
static qboolean R_AllowFlipViewModel( cl_entity_t *e )
{
	if( e == &s_offhandEnt || e == &s_primaryHandEnt )
		return R_HandEntityNeedsMirror( e );

	if( cl_righthand && cl_righthand->value > 0 )
	{
		if( e == tr.viewent )
			return true;
	}

	return false;
}

/*
================
R_StudioComputeBBox

Compute a full bounding box for current sequence
================
*/
static qboolean R_StudioComputeBBox( vec3_t bbox[8] )
{
	cl_entity_t	*e = RI.currententity;

	if( !m_pStudioHeader )
		return false;

	vec3_t mins, maxs;
	// check if we have valid mins\maxs
	if( !VectorIsNull( RI.currentmodel->mins ) && !VectorIsNull( RI.currentmodel->maxs ))
	{
		// clipping bounding box
		VectorCopy( RI.currentmodel->mins, mins );
		VectorCopy( RI.currentmodel->maxs, maxs );
	}
	else
	{
		ClearBounds( mins, maxs );
	}

	// check sequence range
	if( e->curstate.sequence < 0 || e->curstate.sequence >= m_pStudioHeader->numseq )
		e->curstate.sequence = 0;

	mstudioseqdesc_t *pseqdesc = (mstudioseqdesc_t *)((byte *)m_pStudioHeader + m_pStudioHeader->seqindex) + e->curstate.sequence;

	// add sequence box to the model box
	AddPointToBounds( pseqdesc->bbmin, mins, maxs );
	AddPointToBounds( pseqdesc->bbmax, mins, maxs );
	vec3_t studio_mins, studio_maxs;
	ClearBounds( studio_mins, studio_maxs );

	// compute a full bounding box
	for( int i = 0; i < 8; i++ )
	{
		vec3_t p1, p2;
  		p1[0] = ( i & 1 ) ? mins[0] : maxs[0];
  		p1[1] = ( i & 2 ) ? mins[1] : maxs[1];
  		p1[2] = ( i & 4 ) ? mins[2] : maxs[2];

		Matrix3x4_VectorTransform( g_studio.rotationmatrix, p1, p2 );
		AddPointToBounds( p2, studio_mins, studio_maxs );
		if( bbox ) VectorCopy( p2, bbox[i] );
	}

#ifdef XASH_OPENXR
	// Hand presence entities are always near the player's face; skipping the
	// frustum/vis cull guarantees they never pop out of existence.
	if( !bbox && ( e == &s_offhandEnt || e == &s_primaryHandEnt ))
		return true;
#endif

	if( !bbox && R_CullModel( e, studio_mins, studio_maxs ))
		return false; // model culled
	return true; // visible
}

static void R_StudioComputeSkinMatrix( mstudioboneweight_t *boneweights, matrix3x4 result )
{
	int	numbones = 0;

	for( int i = 0; i < MAXSTUDIOBONEWEIGHTS; i++ )
	{
		if( boneweights->bone[i] != -1 )
			numbones++;
	}

	if( numbones == 4 )
	{
		vec4_t *boneMat0 = (vec4_t *)g_studio.worldtransform[boneweights->bone[0]];
		vec4_t *boneMat1 = (vec4_t *)g_studio.worldtransform[boneweights->bone[1]];
		vec4_t *boneMat2 = (vec4_t *)g_studio.worldtransform[boneweights->bone[2]];
		vec4_t *boneMat3 = (vec4_t *)g_studio.worldtransform[boneweights->bone[3]];
		float flWeight0 = boneweights->weight[0] / 255.0f;
		float flWeight1 = boneweights->weight[1] / 255.0f;
		float flWeight2 = boneweights->weight[2] / 255.0f;
		float flWeight3 = boneweights->weight[3] / 255.0f;
		float flTotal = flWeight0 + flWeight1 + flWeight2 + flWeight3;

		if( flTotal < 1.0f ) flWeight0 += 1.0f - flTotal;	// compensate rounding error

		result[0][0] = boneMat0[0][0] * flWeight0 + boneMat1[0][0] * flWeight1 + boneMat2[0][0] * flWeight2 + boneMat3[0][0] * flWeight3;
		result[0][1] = boneMat0[0][1] * flWeight0 + boneMat1[0][1] * flWeight1 + boneMat2[0][1] * flWeight2 + boneMat3[0][1] * flWeight3;
		result[0][2] = boneMat0[0][2] * flWeight0 + boneMat1[0][2] * flWeight1 + boneMat2[0][2] * flWeight2 + boneMat3[0][2] * flWeight3;
		result[0][3] = boneMat0[0][3] * flWeight0 + boneMat1[0][3] * flWeight1 + boneMat2[0][3] * flWeight2 + boneMat3[0][3] * flWeight3;
		result[1][0] = boneMat0[1][0] * flWeight0 + boneMat1[1][0] * flWeight1 + boneMat2[1][0] * flWeight2 + boneMat3[1][0] * flWeight3;
		result[1][1] = boneMat0[1][1] * flWeight0 + boneMat1[1][1] * flWeight1 + boneMat2[1][1] * flWeight2 + boneMat3[1][1] * flWeight3;
		result[1][2] = boneMat0[1][2] * flWeight0 + boneMat1[1][2] * flWeight1 + boneMat2[1][2] * flWeight2 + boneMat3[1][2] * flWeight3;
		result[1][3] = boneMat0[1][3] * flWeight0 + boneMat1[1][3] * flWeight1 + boneMat2[1][3] * flWeight2 + boneMat3[1][3] * flWeight3;
		result[2][0] = boneMat0[2][0] * flWeight0 + boneMat1[2][0] * flWeight1 + boneMat2[2][0] * flWeight2 + boneMat3[2][0] * flWeight3;
		result[2][1] = boneMat0[2][1] * flWeight0 + boneMat1[2][1] * flWeight1 + boneMat2[2][1] * flWeight2 + boneMat3[2][1] * flWeight3;
		result[2][2] = boneMat0[2][2] * flWeight0 + boneMat1[2][2] * flWeight1 + boneMat2[2][2] * flWeight2 + boneMat3[2][2] * flWeight3;
		result[2][3] = boneMat0[2][3] * flWeight0 + boneMat1[2][3] * flWeight1 + boneMat2[2][3] * flWeight2 + boneMat3[2][3] * flWeight3;
	}
	else if( numbones == 3 )
	{
		vec4_t *boneMat0 = (vec4_t *)g_studio.worldtransform[boneweights->bone[0]];
		vec4_t *boneMat1 = (vec4_t *)g_studio.worldtransform[boneweights->bone[1]];
		vec4_t *boneMat2 = (vec4_t *)g_studio.worldtransform[boneweights->bone[2]];
		float flWeight0 = boneweights->weight[0] / 255.0f;
		float flWeight1 = boneweights->weight[1] / 255.0f;
		float flWeight2 = boneweights->weight[2] / 255.0f;
		float flTotal = flWeight0 + flWeight1 + flWeight2;

		if( flTotal < 1.0f ) flWeight0 += 1.0f - flTotal;	// compensate rounding error

		result[0][0] = boneMat0[0][0] * flWeight0 + boneMat1[0][0] * flWeight1 + boneMat2[0][0] * flWeight2;
		result[0][1] = boneMat0[0][1] * flWeight0 + boneMat1[0][1] * flWeight1 + boneMat2[0][1] * flWeight2;
		result[0][2] = boneMat0[0][2] * flWeight0 + boneMat1[0][2] * flWeight1 + boneMat2[0][2] * flWeight2;
		result[0][3] = boneMat0[0][3] * flWeight0 + boneMat1[0][3] * flWeight1 + boneMat2[0][3] * flWeight2;
		result[1][0] = boneMat0[1][0] * flWeight0 + boneMat1[1][0] * flWeight1 + boneMat2[1][0] * flWeight2;
		result[1][1] = boneMat0[1][1] * flWeight0 + boneMat1[1][1] * flWeight1 + boneMat2[1][1] * flWeight2;
		result[1][2] = boneMat0[1][2] * flWeight0 + boneMat1[1][2] * flWeight1 + boneMat2[1][2] * flWeight2;
		result[1][3] = boneMat0[1][3] * flWeight0 + boneMat1[1][3] * flWeight1 + boneMat2[1][3] * flWeight2;
		result[2][0] = boneMat0[2][0] * flWeight0 + boneMat1[2][0] * flWeight1 + boneMat2[2][0] * flWeight2;
		result[2][1] = boneMat0[2][1] * flWeight0 + boneMat1[2][1] * flWeight1 + boneMat2[2][1] * flWeight2;
		result[2][2] = boneMat0[2][2] * flWeight0 + boneMat1[2][2] * flWeight1 + boneMat2[2][2] * flWeight2;
		result[2][3] = boneMat0[2][3] * flWeight0 + boneMat1[2][3] * flWeight1 + boneMat2[2][3] * flWeight2;
	}
	else if( numbones == 2 )
	{
		vec4_t *boneMat0 = (vec4_t *)g_studio.worldtransform[boneweights->bone[0]];
		vec4_t *boneMat1 = (vec4_t *)g_studio.worldtransform[boneweights->bone[1]];
		float flWeight0 = boneweights->weight[0] / 255.0f;
		float flWeight1 = boneweights->weight[1] / 255.0f;
		float flTotal = flWeight0 + flWeight1;

		if( flTotal < 1.0f ) flWeight0 += 1.0f - flTotal;	// compensate rounding error

		result[0][0] = boneMat0[0][0] * flWeight0 + boneMat1[0][0] * flWeight1;
		result[0][1] = boneMat0[0][1] * flWeight0 + boneMat1[0][1] * flWeight1;
		result[0][2] = boneMat0[0][2] * flWeight0 + boneMat1[0][2] * flWeight1;
		result[0][3] = boneMat0[0][3] * flWeight0 + boneMat1[0][3] * flWeight1;
		result[1][0] = boneMat0[1][0] * flWeight0 + boneMat1[1][0] * flWeight1;
		result[1][1] = boneMat0[1][1] * flWeight0 + boneMat1[1][1] * flWeight1;
		result[1][2] = boneMat0[1][2] * flWeight0 + boneMat1[1][2] * flWeight1;
		result[1][3] = boneMat0[1][3] * flWeight0 + boneMat1[1][3] * flWeight1;
		result[2][0] = boneMat0[2][0] * flWeight0 + boneMat1[2][0] * flWeight1;
		result[2][1] = boneMat0[2][1] * flWeight0 + boneMat1[2][1] * flWeight1;
		result[2][2] = boneMat0[2][2] * flWeight0 + boneMat1[2][2] * flWeight1;
		result[2][3] = boneMat0[2][3] * flWeight0 + boneMat1[2][3] * flWeight1;
	}
	else
	{
		Matrix3x4_Copy( result, g_studio.worldtransform[boneweights->bone[0]] );
	}
}

/*
===============
pfnGetCurrentEntity

===============
*/
static cl_entity_t *pfnGetCurrentEntity( void )
{
	return RI.currententity;
}

/*
===============
pfnPlayerInfo

===============
*/
player_info_t *pfnPlayerInfo( int index )
{
	if( !FBitSet( RI.rvp.flags, RF_DRAW_WORLD ))
		index = -1;

	return gEngfuncs.pfnPlayerInfo( index );
}

/*
===============
pfnGetPlayerState

===============
*/
static entity_state_t *R_StudioGetPlayerState( int index )
{
	if( !FBitSet( RI.rvp.flags, RF_DRAW_WORLD ) && RI.currententity )
		return &RI.currententity->curstate;

	return gEngfuncs.pfnGetPlayerState( index );
}

/*
===============
pfnGetEngineTimes

===============
*/
static void pfnGetEngineTimes( int *framecount, double *current, double *old )
{
	if( framecount ) *framecount = tr.realframecount;
	if( current ) *current = gp_cl->time;
	if( old ) *old =   gp_cl->oldtime;
}

/*
===============
pfnGetViewInfo

===============
*/
static void pfnGetViewInfo( float *origin, float *upv, float *rightv, float *forwardv )
{
	if( origin ) VectorCopy( RI.rvp.vieworigin, origin );
	if( forwardv ) VectorCopy( RI.vforward, forwardv );
	if( rightv ) VectorCopy( RI.vright, rightv );
	if( upv ) VectorCopy( RI.vup, upv );
}

/*
===============
pfnGetModelCounters

===============
*/
static void pfnGetModelCounters( int **s, int **a )
{
	*s = &g_studio.framecount;
	*a = &r_stats.c_studio_models_drawn;
}

/*
===============
pfnStudioGetBoneTransform

===============
*/
static float ****pfnStudioGetBoneTransform( void )
{
	return (float ****)g_studio.bonestransform;
}

/*
===============
pfnStudioGetLightTransform

===============
*/
static float ****pfnStudioGetLightTransform( void )
{
	return (float ****)g_studio.lighttransform;
}

/*
===============
pfnStudioGetRotationMatrix

===============
*/
static float ***pfnStudioGetRotationMatrix( void )
{
	return (float ***)g_studio.rotationmatrix;
}

/*
====================
StudioPlayerBlend

====================
*/
static void R_StudioPlayerBlend( mstudioseqdesc_t *pseqdesc, int *pBlend, float *pPitch )
{
	// calc up/down pointing
	*pBlend = (*pPitch * 3.0f);

	if( *pBlend < pseqdesc->blendstart[0] )
	{
		*pPitch -= pseqdesc->blendstart[0] / 3.0f;
		*pBlend = 0;
	}
	else if( *pBlend > pseqdesc->blendend[0] )
	{
		*pPitch -= pseqdesc->blendend[0] / 3.0f;
		*pBlend = 255;
	}
	else
	{
		if( pseqdesc->blendend[0] - pseqdesc->blendstart[0] < 0.1f ) // catch qc error
			*pBlend = 127;
		else *pBlend = 255 * (*pBlend - pseqdesc->blendstart[0]) / (pseqdesc->blendend[0] - pseqdesc->blendstart[0]);
		*pPitch = 0.0f;
	}
}

/*
====================
R_StudioLerpMovement

====================
*/
void R_StudioLerpMovement( cl_entity_t *e, double time, vec3_t origin, vec3_t angles )
{
	float	f = 1.0f;

	// don't do it if the goalstarttime hasn't updated in a while.
	// NOTE: Because we need to interpolate multiplayer characters, the interpolation time limit
	// was increased to 1.0 s., which is 2x the max lag we are accounting for.
	if( g_studio.interpolate && ( time < e->curstate.animtime + 1.0f ) && ( e->curstate.animtime != e->latched.prevanimtime ))
		f = ( time - e->curstate.animtime ) / ( e->curstate.animtime - e->latched.prevanimtime );

	// Con_Printf( "%4.2f %.2f %.2f\n", f, e->curstate.animtime, g_studio.time );
	VectorLerp( e->latched.prevorigin, f, e->curstate.origin, origin );

	if( !VectorCompareEpsilon( e->curstate.angles, e->latched.prevangles, ON_EPSILON ))
	{
		vec4_t	q, q1, q2;
		AngleQuaternion( e->curstate.angles, q1, false );
		AngleQuaternion( e->latched.prevangles, q2, false );
		QuaternionSlerp( q2, q1, f, q );
		QuaternionAngle( q, angles );
	}
	else VectorCopy( e->curstate.angles, angles );
}

/*
====================
StudioSetUpTransform

====================
*/
static void R_StudioSetUpTransform( cl_entity_t *e )
{
	vec3_t origin = Vec3( e->origin );
	vec3_t angles = Vec3( e->angles );

	// interpolate monsters position (moved into UpdateEntityFields by user request)
	if( e->curstate.movetype == MOVETYPE_STEP && !FBitSet( gp_host->features, ENGINE_COMPUTE_STUDIO_LERP ))
	{
		R_StudioLerpMovement( e, g_studio.time, origin, angles );
	}

	if( !FBitSet( gp_host->features, ENGINE_COMPENSATE_QUAKE_BUG ))
		angles[PITCH] = -angles[PITCH]; // stupid quake bug

	// don't rotate clients, only aim
	if( e->player ) angles[PITCH] = 0.0f;

#ifdef XASH_OPENXR
	if( e == tr.viewent && XR_IsActive() )
	{
		vec3_t handOrigin, handAngles;
		if( XR_GetPrimaryHandTransform( handOrigin, handAngles ))
		{
			float scale = (vr_worldscale && vr_worldscale->value > 0.0f) ? vr_worldscale->value : 40.0f;
			float turn_yaw = XR_GetPlayerTurnYaw();

			const char *wpn = ( e->model && e->model->name[0] ) ? e->model->name : "";
			XR_GetWeaponPose( wpn, handOrigin, handAngles, turn_yaw, RI.rvp.vieworigin, scale, origin, angles );

			// Cache raw physical 6DoF hand pose for calibration debug visualizer
			// (world hand position + aim angles, before grip offsets)
			{
				float yaw_rad = DEG2RAD( turn_yaw );
				float cy = cosf( yaw_rad );
				float sy = sinf( yaw_rad );

				s_vrDebugRawHandOrigin[0] = RI.rvp.vieworigin[0] + (handOrigin[0] * cy - handOrigin[1] * sy) * scale;
				s_vrDebugRawHandOrigin[1] = RI.rvp.vieworigin[1] + (handOrigin[0] * sy + handOrigin[1] * cy) * scale;
				s_vrDebugRawHandOrigin[2] = RI.rvp.vieworigin[2] + handOrigin[2] * scale;

				// Historical behavior: the debug gizmo shows the aim angles
				// including the per-weapon calibration adjustments.
				VectorCopy( angles, s_vrDebugRawHandAngles );
			}
			s_vrDebugHandActive = true;

			if( e->model && vr_lefthanded && vr_lefthanded->value > 0.0f &&
			    ( !vr_lefthanded_mirror_grip || vr_lefthanded_mirror_grip->value > 0.0f ))
			{
				static model_t *s_lastMirrorLog = NULL;
				if( s_lastMirrorLog != e->model )
				{
					s_lastMirrorLog = e->model;
					gEngfuncs.Con_DPrintf( "[VR_GRIP] src=renderer model=%s lefthanded=1 mirror=1\n", e->model->name );
				}
			}

			// Pull the weapon toward the eye when its grip would sit inside a
			// wall. PM_STUDIO_IGNORE keeps the viewmodel itself from blocking
			// the trace.
			static cvar_t *vr_weapon_pullback = NULL;
			if( !vr_weapon_pullback ) vr_weapon_pullback = gEngfuncs.pfnGetCvarPointer( "vr_weapon_pullback" );

			float pullback_active = 0.0f;
			if( vr_weapon_pullback && vr_weapon_pullback->value > 0.0f && gEngfuncs.CL_TraceLine )
			{
				vec3_t eye = Vec3( RI.rvp.vieworigin );
				pmtrace_t tr = gEngfuncs.CL_TraceLine( eye, origin, PM_STUDIO_IGNORE );

				if( tr.fraction < 1.0f )
				{
					vec3_t dir;
					float dist = VectorDistance( eye, origin );
					float allowed = dist * tr.fraction - 4.0f;

					if( allowed < 8.0f ) allowed = 8.0f;

					VectorSubtract( origin, eye, dir );
					VectorNormalize( dir );
					VectorMA( eye, allowed, dir, origin );
					pullback_active = 1.0f;
				}
			}

			VectorCopy( origin, e->origin );
			VectorCopy( angles, e->angles );

			gEngfuncs.Con_DPrintf( "[VR_GRIP] src=renderer model=%s origin=(%.2f %.2f %.2f) angles=(%.2f %.2f %.2f) lefthanded=%d pullback=%d\n",
				wpn, origin[0], origin[1], origin[2], angles[0], angles[1], angles[2],
				(vr_lefthanded && vr_lefthanded->value > 0.0f) ? 1 : 0, (int)pullback_active );
		}
	}
	else if( ( e == &s_offhandEnt || e == &s_primaryHandEnt ) && XR_IsActive() )
	{
		vec3_t handOrigin, handAngles;
		int hand = ( e == &s_primaryHandEnt ) ? R_VR_PrimaryHandIndex() : R_VR_SecondaryHandIndex();

		if( XR_GetHandPresenceTransform( hand, handOrigin, handAngles ))
		{
			float scale = (vr_worldscale && vr_worldscale->value > 0.0f) ? vr_worldscale->value : 40.0f;
			float turn_yaw = XR_GetPlayerTurnYaw();
			float yaw_rad = DEG2RAD( turn_yaw );
			float cy = cosf( yaw_rad );
			float sy = sinf( yaw_rad );

			// Rotate local hand displacement by the player's world yaw orientation
			float world_dx = (handOrigin[0] * cy - handOrigin[1] * sy) * scale;
			float world_dy = (handOrigin[0] * sy + handOrigin[1] * cy) * scale;
			float world_dz = handOrigin[2] * scale;

			origin[0] = RI.rvp.vieworigin[0] + world_dx;
			origin[1] = RI.rvp.vieworigin[1] + world_dy;
			origin[2] = RI.rvp.vieworigin[2] + world_dz;

			angles[0] = handAngles[0];
			angles[1] = anglemod( handAngles[1] + turn_yaw );
			angles[2] = handAngles[2];

			// The standalone two-hand model is centered on the palm, which is
			// the same anchor as the tracked controller grip, so the default
			// offsets are zero. The cvars remain for per-user fine tuning.
			{
				float off_fwd = vr_hand_offset_forward ? vr_hand_offset_forward->value : 0.0f;
				float off_rt  = vr_hand_offset_right ? vr_hand_offset_right->value : 0.0f;
				float off_up  = vr_hand_offset_up ? vr_hand_offset_up->value : 0.0f;

				if( off_fwd != 0.0f || off_rt != 0.0f || off_up != 0.0f )
				{
					vec3_t fwd, rt, up;
					AngleVectors( angles, fwd, rt, up );
					VectorMA( origin, off_fwd, fwd, origin );
					VectorMA( origin, off_rt, rt, origin );
					VectorMA( origin, off_up, up, origin );
				}
			}

			if( e == &s_offhandEnt )
			{
				// Cache raw secondary 6DoF hand pose for calibration debug visualizer
				VectorCopy( origin, s_vrDebugOffHandOrigin );
				VectorCopy( angles, s_vrDebugOffHandAngles );
				s_vrDebugOffHandActive = true;
			}

			// Two-handed foregrip socket: while the off-hand is gripping the
			// weapon, snap its palm to the weapon's foregrip landmark instead of
			// leaving it at the physical controller position.
			if( e == &s_offhandEnt && R_VR_OffHandAttachedToWeapon( ))
			{
				static cvar_t *vr_foregrip = NULL;
				if( !vr_foregrip ) vr_foregrip = gEngfuncs.pfnGetCvarPointer( "vr_foregrip" );
				const char *wpn = ( tr.viewent && tr.viewent->model && tr.viewent->model->name[0] ) ? tr.viewent->model->name : "";
				vec3_t fg_off, fg_rot;

				if( vr_foregrip && vr_foregrip->value > 0.0f && wpn[0] &&
				    XR_GetWeaponForegrip( wpn, fg_off, fg_rot ))
				{
					vec3_t ph_origin, ph_angles, wpn_origin, wpn_angles;
					if( XR_GetPrimaryHandTransform( ph_origin, ph_angles ))
					{
						XR_GetWeaponPose( wpn, ph_origin, ph_angles, turn_yaw, RI.rvp.vieworigin, scale,
							wpn_origin, wpn_angles );

						vec3_t fg_fwd, fg_rt, fg_up;
						AngleVectors( wpn_angles, fg_fwd, fg_rt, fg_up );

						origin[0] = wpn_origin[0] + fg_fwd[0] * fg_off[0] + fg_rt[0] * fg_off[1] + fg_up[0] * fg_off[2];
						origin[1] = wpn_origin[1] + fg_fwd[1] * fg_off[0] + fg_rt[1] * fg_off[1] + fg_up[1] * fg_off[2];
						origin[2] = wpn_origin[2] + fg_fwd[2] * fg_off[0] + fg_rt[2] * fg_off[1] + fg_up[2] * fg_off[2];

						XR_ComposeLocalRotation( wpn_angles, fg_rot, angles );

						gEngfuncs.Con_DPrintf( "[VR_FOREGRIP] model=%s origin=(%.2f %.2f %.2f) angles=(%.2f %.2f %.2f)\n",
							wpn, origin[0], origin[1], origin[2], angles[0], angles[1], angles[2] );
					}
				}
			}

			VectorCopy( origin, e->origin );
			VectorCopy( angles, e->angles );
		}
	}
#endif

	Matrix3x4_CreateFromEntity( g_studio.rotationmatrix, angles, origin, 1.0f );

	// Mirrored viewmodels (cl_righthand) and right-controller hands flip the
	// local Y axis so the mesh remains anatomically correct.
	if( R_AllowFlipViewModel( e ))
	{
		g_studio.rotationmatrix[0][1] = -g_studio.rotationmatrix[0][1];
		g_studio.rotationmatrix[1][1] = -g_studio.rotationmatrix[1][1];
		g_studio.rotationmatrix[2][1] = -g_studio.rotationmatrix[2][1];
	}
}

/*
====================
StudioEstimateFrame

====================
*/
float R_StudioEstimateFrame( cl_entity_t *e, mstudioseqdesc_t *pseqdesc, double time )
{
	double	dfdt, f;

	if( g_studio.interpolate )
	{
		if( time < e->curstate.animtime ) dfdt = 0.0;
		else dfdt = (time - e->curstate.animtime) * e->curstate.framerate * pseqdesc->fps;
	}
	else dfdt = 0;

	if( pseqdesc->numframes <= 1 ) f = 0.0;
	else f = (e->curstate.frame * (pseqdesc->numframes - 1)) / 256.0f;

	f += dfdt;

	if( pseqdesc->flags & STUDIO_LOOPING )
	{
		if( pseqdesc->numframes > 1 )
			f -= (int)(f / (pseqdesc->numframes - 1)) *  (pseqdesc->numframes - 1);
		if( f < 0 ) f += (pseqdesc->numframes - 1);
	}
	else
	{
		if( f >= pseqdesc->numframes - 1.001 )
			f = pseqdesc->numframes - 1.001;
		if( f < 0.0 )  f = 0.0;
	}
	return f;
}

/*
====================
StudioEstimateInterpolant

====================
*/
static float R_StudioEstimateInterpolant( cl_entity_t *e )
{
	float	dadt = 1.0f;

	if( g_studio.interpolate && ( e->curstate.animtime >= e->latched.prevanimtime + 0.01f ))
	{
		dadt = ( g_studio.time - e->curstate.animtime ) / 0.1f;
		if( dadt > 2.0f ) dadt = 2.0f;
	}

	return dadt;
}

/*
====================
StudioFxTransform

====================
*/
static void R_StudioFxTransform( cl_entity_t *ent, matrix3x4 transform )
{
	switch( ent->curstate.renderfx )
	{
	case kRenderFxDistort:
	case kRenderFxHologram:
		if( !gEngfuncs.COM_RandomLong( 0, 49 ))
		{
			int	axis = gEngfuncs.COM_RandomLong( 0, 1 );

			if( axis == 1 ) axis = 2; // choose between x & z
			VectorScale( transform[axis], gEngfuncs.COM_RandomFloat( 1.0f, 1.484f ), transform[axis] );
		}
		else if( !gEngfuncs.COM_RandomLong( 0, 49 ))
		{
			int	axis = gEngfuncs.COM_RandomLong( 0, 1 );

			if( axis == 1 ) axis = 2; // choose between x & z
			float offset = gEngfuncs.COM_RandomFloat( -10.0f, 10.0f );
			transform[gEngfuncs.COM_RandomLong( 0, 2 )][3] += offset;
		}
		break;
	case kRenderFxExplode:
		{
			float scale = 1.0f + ( g_studio.time - ent->curstate.animtime ) * 10.0f;
			if( scale > 2.0f ) scale = 2.0f; // don't blow up more than 200%

			transform[0][1] *= scale;
			transform[1][1] *= scale;
			transform[2][1] *= scale;
		}
		break;
	}
}

/*
====================
StudioCalcBoneAdj

====================
*/
static void R_StudioCalcBoneAdj( float dadt, float *adj, const byte *pcontroller1, const byte *pcontroller2, byte mouthopen )
{
	mstudiobonecontroller_t	*pbonecontroller = (mstudiobonecontroller_t *)((byte *)m_pStudioHeader + m_pStudioHeader->bonecontrollerindex);

	for( int j = 0; j < m_pStudioHeader->numbonecontrollers; j++ )
	{
		float value = 0.0f;
		int i = pbonecontroller[j].index;

		if( i == STUDIO_MOUTH )
		{
			// mouth hardcoded at controller 4
			value = (float)mouthopen / 64.0f;
			value = bound( 0.0f, value, 1.0f );
			value = (1.0f - value) * pbonecontroller[j].start + value * pbonecontroller[j].end;
		}
		else if( i < 4 )
		{
			// check for 360% wrapping
			if( FBitSet( pbonecontroller[j].type, STUDIO_RLOOP ))
			{
				if( abs( pcontroller1[i] - pcontroller2[i] ) > 128 )
				{
					int a = (pcontroller1[i] + 128) % 256;
					int b = (pcontroller2[i] + 128) % 256;
					value = (( a * dadt ) + ( b * ( 1.0f - dadt )) - 128) * (360.0f / 256.0f) + pbonecontroller[j].start;
				}
				else
				{
					value = ((pcontroller1[i] * dadt + (pcontroller2[i]) * (1.0f - dadt))) * (360.0f / 256.0f) + pbonecontroller[j].start;
				}
			}
			else
			{
				value = (pcontroller1[i] * dadt + pcontroller2[i] * (1.0f - dadt)) / 255.0f;
				value = bound( 0.0f, value, 1.0f );
				value = (1.0f - value) * pbonecontroller[j].start + value * pbonecontroller[j].end;
			}
		}

		switch( pbonecontroller[j].type & STUDIO_TYPES )
		{
		case STUDIO_XR:
		case STUDIO_YR:
		case STUDIO_ZR:
			adj[j] = DEG2RAD( value );
			break;
		case STUDIO_X:
		case STUDIO_Y:
		case STUDIO_Z:
			adj[j] = value;
			break;
		}
	}
}

/*
====================
StudioCalcRotations

====================
*/
static void R_StudioCalcRotations( cl_entity_t *e, float pos[][3], vec4_t *q, mstudioseqdesc_t *pseqdesc, mstudioanim_t *panim, float f )
{
	float adj[MAXSTUDIOCONTROLLERS];

	// bah, fix this bug with changing sequences too fast
	if( f > pseqdesc->numframes - 1 )
	{
		f = 0.0f;
	}
	else if( f < -0.01f )
	{
		// BUG ( somewhere else ) but this code should validate this data.
		// This could cause a crash if the frame # is negative, so we'll go ahead
		// and clamp it here
		f = -0.01f;
	}

	int frame = (int)f;
	float dadt = R_StudioEstimateInterpolant( e );
	float s = (f - frame);

	// add in programtic controllers
	mstudiobone_t *pbone = (mstudiobone_t *)((byte *)m_pStudioHeader + m_pStudioHeader->boneindex);

	R_StudioCalcBoneAdj( dadt, adj, e->curstate.controller, e->latched.prevcontroller, e->mouth.mouthopen );

	for( int i = 0; i < m_pStudioHeader->numbones; i++, pbone++, panim++ )
		R_StudioCalcBones( frame, s, pbone, panim, adj, pos[i], q[i] );

	if( pseqdesc->motiontype & STUDIO_X ) pos[pseqdesc->motionbone][0] = 0.0f;
	if( pseqdesc->motiontype & STUDIO_Y ) pos[pseqdesc->motionbone][1] = 0.0f;
	if( pseqdesc->motiontype & STUDIO_Z ) pos[pseqdesc->motionbone][2] = 0.0f;
}

/*
====================
StudioMergeBones

====================
*/
static void R_StudioMergeBones( cl_entity_t *e, model_t *m_pSubModel )
{
	static vec4_t	q[MAXSTUDIOBONES];
	static float	pos[MAXSTUDIOBONES][3];

	if( e->curstate.sequence >=  m_pStudioHeader->numseq )
		e->curstate.sequence = 0;

	mstudioseqdesc_t *pseqdesc = (mstudioseqdesc_t *)((byte *)m_pStudioHeader + m_pStudioHeader->seqindex) + e->curstate.sequence;
	float f = R_StudioEstimateFrame( e, pseqdesc, g_studio.time );

	mstudioanim_t *panim = gEngfuncs.R_StudioGetAnim( m_pStudioHeader, m_pSubModel, pseqdesc );
	R_StudioCalcRotations( e, pos, q, pseqdesc, panim, f );
	mstudiobone_t *pbones = (mstudiobone_t *)((byte *)m_pStudioHeader + m_pStudioHeader->boneindex);

	for( int i = 0; i < m_pStudioHeader->numbones; i++ )
	{
		int j;
		for( j = 0; j < g_studio.cached_numbones; j++ )
		{
			if( !Q_stricmp( pbones[i].name, g_studio.cached_bonenames[j] ))
			{
				Matrix3x4_Copy( g_studio.bonestransform[i], g_studio.cached_bonestransform[j] );
				Matrix3x4_Copy( g_studio.lighttransform[i], g_studio.cached_lighttransform[j] );
				break;
			}
		}

		if( j >= g_studio.cached_numbones )
		{
			matrix3x4 bonematrix;
			Matrix3x4_FromOriginQuat( bonematrix, q[i], pos[i] );
			if( pbones[i].parent == -1 )
			{
				Matrix3x4_ConcatTransforms( g_studio.bonestransform[i], g_studio.rotationmatrix, bonematrix );
				Matrix3x4_Copy( g_studio.lighttransform[i], g_studio.bonestransform[i] );

				// apply client-side effects to the transformation matrix
				R_StudioFxTransform( e, g_studio.bonestransform[i] );
			}
			else
			{
				Matrix3x4_ConcatTransforms( g_studio.bonestransform[i], g_studio.bonestransform[pbones[i].parent], bonematrix );
				Matrix3x4_ConcatTransforms( g_studio.lighttransform[i], g_studio.lighttransform[pbones[i].parent], bonematrix );
			}
		}
	}
}

#ifdef XASH_OPENXR
/*
====================
R_StudioApplyFingerCurling

Applies procedural finger bone curling based on OpenXR analog triggers (index finger),
grips (middle/ring/pinky fingers), and thumb touch/button states.
====================
*/
static void R_StudioApplyFingerCurling( cl_entity_t *e, int numbones, mstudiobone_t *pbones, vec4_t *q )
{
	if( !XR_IsActive() )
		return;

	if( vr_finger_curling && vr_finger_curling->value <= 0.0f )
		return;

	float scale = (vr_finger_curl_scale && vr_finger_curl_scale->value > 0.0f) ? vr_finger_curl_scale->value : 1.0f;

	float trigL = 0.0f, gripL = 0.0f, thmbL = 0.0f;
	float trigR = 0.0f, gripR = 0.0f, thmbR = 0.0f;
	XR_GetFingerCurlAxes( VR_HAND_LEFT,  &trigL, &gripL, &thmbL );
	XR_GetFingerCurlAxes( VR_HAND_RIGHT, &trigR, &gripR, &thmbR );

	int curls_applied = 0;

	for( int i = 0; i < numbones; i++ )
	{
		const char *name = pbones[i].name;
		if( !name ) continue;

		// The viewmodel and the primary hand entity are driven by the primary
		// controller; the off-hand entity by the secondary controller. The
		// two-hand model draws the chain that matches its controller, so the
		// analog source follows the entity rather than the bone name.
		qboolean is_left = ( e == &s_offhandEnt )
			? !( vr_lefthanded && vr_lefthanded->value > 0.0f )
			: ( vr_lefthanded && vr_lefthanded->value > 0.0f );

		float trg = is_left ? trigL : trigR;
		float grp = is_left ? gripL : gripR;
		float thm = is_left ? thmbL : thmbR;

		float curl_angle = 0.0f;

		// Thumb: Finger0, Finger01, Finger02 / Bone27, Bone28, Bone29
		if( Q_stristr( name, "Finger0" ) || Q_stristr( name, "Thumb" ) || !Q_strcmp( name, "Bone27" ) || !Q_strcmp( name, "Bone28" ) || !Q_strcmp( name, "Bone29" ) )
		{
			// Compare the last two characters, not a substring: "Bip01"
			// itself contains "01", which misclassifies the thumb base.
			const int nl = Q_strlen( name );
			const qboolean ends01 = ( nl >= 2 && name[nl-2] == '0' && name[nl-1] == '1' );
			const qboolean ends02 = ( nl >= 2 && name[nl-2] == '0' && name[nl-1] == '2' );
			if( ends02 || !Q_strcmp( name, "Bone29" ) )
				curl_angle = 0.50f * thm * scale;
			else if( ends01 || !Q_strcmp( name, "Bone28" ) )
				curl_angle = 0.55f * thm * scale;
			else
				curl_angle = 0.35f * thm * scale;
		}
		// Index finger: Finger1, Finger11, Finger12 / Bone31, Bone32, Bone33
		else if( Q_stristr( name, "Finger1" ) || Q_stristr( name, "Index" ) || !Q_strcmp( name, "Bone31" ) || !Q_strcmp( name, "Bone32" ) || !Q_strcmp( name, "Bone33" ) )
		{
			if( Q_stristr( name, "12" ) || !Q_strcmp( name, "Bone33" ) )
				curl_angle = 0.65f * trg * scale;
			else if( Q_stristr( name, "11" ) || !Q_strcmp( name, "Bone32" ) )
				curl_angle = 0.85f * trg * scale;
			else
				curl_angle = 0.55f * trg * scale;
		}
		// Middle finger: Finger2, Finger21, Finger22 / Bone35, Bone36, Bone37
		else if( Q_stristr( name, "Finger2" ) || Q_stristr( name, "Middle" ) || !Q_strcmp( name, "Bone35" ) || !Q_strcmp( name, "Bone36" ) || !Q_strcmp( name, "Bone37" ) )
		{
			if( Q_stristr( name, "22" ) || !Q_strcmp( name, "Bone37" ) )
				curl_angle = 0.65f * grp * scale;
			else if( Q_stristr( name, "21" ) || !Q_strcmp( name, "Bone36" ) )
				curl_angle = 0.85f * grp * scale;
			else
				curl_angle = 0.55f * grp * scale;
		}
		// Ring finger: Finger3, Finger31, Finger32 / Bone39, Bone40, Bone41
		else if( Q_stristr( name, "Finger3" ) || Q_stristr( name, "Ring" ) || !Q_strcmp( name, "Bone39" ) || !Q_strcmp( name, "Bone40" ) || !Q_strcmp( name, "Bone41" ) )
		{
			if( Q_stristr( name, "32" ) || !Q_strcmp( name, "Bone41" ) )
				curl_angle = 0.65f * grp * scale;
			else if( Q_stristr( name, "31" ) || !Q_strcmp( name, "Bone40" ) )
				curl_angle = 0.85f * grp * scale;
			else
				curl_angle = 0.55f * grp * scale;
		}
		// Pinky finger: Finger4, Finger41, Finger42 / Bone43, Bone44, Bone45
		else if( Q_stristr( name, "Finger4" ) || Q_stristr( name, "Pinky" ) || !Q_strcmp( name, "Bone43" ) || !Q_strcmp( name, "Bone44" ) || !Q_strcmp( name, "Bone45" ) )
		{
			if( Q_stristr( name, "42" ) || !Q_strcmp( name, "Bone45" ) )
				curl_angle = 0.65f * grp * scale;
			else if( Q_stristr( name, "41" ) || !Q_strcmp( name, "Bone44" ) )
				curl_angle = 0.85f * grp * scale;
			else
				curl_angle = 0.55f * grp * scale;
		}
		else
		{
			continue;
		}

		if( curl_angle > 0.001f )
		{
			float half_a = curl_angle * 0.5f;
			if( R_AllowFlipViewModel( e ))
				half_a = -half_a; // a reflection inverts the curl direction
			float s = sinf( half_a );
			float c = cosf( half_a );

			float qx = q[i][0], qy = q[i][1], qz = q[i][2], qw = q[i][3];

			if( e == &s_offhandEnt || e == &s_primaryHandEnt )
			{
				// Rimrook two-hand rig: the finger bones' local Y axis is the
				// curl axis. Their local Z is the palm normal (rotating around
				// it bends the fingers sideways instead of closing the fist).
				// Post-multiply by delta_q = (0, s, 0, c) for a local Y rotation.
				q[i][0] = qx * c - qz * s;
				q[i][1] = qw * s + qy * c;
				q[i][2] = qx * s + qz * c;
				q[i][3] = qw * c - qy * s;
			}
			else
			{
				// Valve viewmodel rigs curl around the bone's local Z axis.
				// Post-multiply quaternion q[i] by delta_q = (0, 0, s, c).
				q[i][0] = qx * c + qy * s;
				q[i][1] = qy * c - qx * s;
				q[i][2] = qz * c + qw * s;
				q[i][3] = qw * c - qz * s;
			}

			curls_applied++;
		}
	}

	static float s_lastDbgTime = -10.0f;
	static float s_lastTrig = -1.0f, s_lastGrip = -1.0f;
	qboolean changed = (fabsf(trigR - s_lastTrig) > 0.05f || fabsf(gripR - s_lastGrip) > 0.05f);

	if( curls_applied > 0 && (changed || g_studio.time - s_lastDbgTime > 1.0f) )
	{
		s_lastDbgTime = g_studio.time;
		s_lastTrig = trigR;
		s_lastGrip = gripR;
		gEngfuncs.Con_Printf( "^2[VR_HANDS_DBG] Finger curling active: %d bones curled (trigR=%.2f gripR=%.2f thmbR=%.2f | trigL=%.2f gripL=%.2f thmbL=%.2f)\n",
			curls_applied, trigR, gripR, thmbR, trigL, gripL, thmbL );
	}
}
#endif

/*
====================
R_StudioFindSequence

Returns the index of the first sequence whose label contains the given
case-insensitive substring, or -1 when it is not present.
====================
*/
static int R_StudioFindSequence( studiohdr_t *header, const char *name )
{
	if( !header || !name || !name[0] )
		return -1;

	mstudioseqdesc_t *seq = (mstudioseqdesc_t *)((byte *)header + header->seqindex);

	for( int i = 0; i < header->numseq; i++ )
	{
		if( seq[i].label[0] && Q_stristr( seq[i].label, name ))
			return i;
	}

	return -1;
}

/*
====================
StudioSetupBones

====================
*/
static void R_StudioSetupBones( cl_entity_t *e )
{
	static vec3_t	pos[MAXSTUDIOBONES];
	static vec4_t	q[MAXSTUDIOBONES];
	static vec3_t	pos2[MAXSTUDIOBONES];
	static vec4_t	q2[MAXSTUDIOBONES];
	static vec3_t	pos3[MAXSTUDIOBONES];
	static vec4_t	q3[MAXSTUDIOBONES];
	static vec3_t	pos4[MAXSTUDIOBONES];
	static vec4_t	q4[MAXSTUDIOBONES];
	qboolean	skip_sequence_blend = false;

	if( e->curstate.sequence >= m_pStudioHeader->numseq )
		e->curstate.sequence = 0;

	mstudioseqdesc_t *pseqdesc = (mstudioseqdesc_t *)((byte *)m_pStudioHeader + m_pStudioHeader->seqindex) + e->curstate.sequence;
	float f = R_StudioEstimateFrame( e, pseqdesc, g_studio.time );

#ifdef XASH_OPENXR
	if( (e == tr.viewent) && XR_IsActive() )
	{
		static cvar_t *vr_weapon_idle_mode = NULL;
		if( !vr_weapon_idle_mode ) vr_weapon_idle_mode = gEngfuncs.pfnGetCvarPointer( "vr_weapon_idle_mode" );
		// Steady VR hand mode: freeze idle and fidget sequences at frame 0 (resting ready pose)
		if( !vr_weapon_idle_mode || vr_weapon_idle_mode->value == 0.0f )
		{
			if( Q_stristr( pseqdesc->label, "idle" ) || Q_stristr( pseqdesc->label, "fidget" ) )
			{
				f = 0.0f;
			}
		}

		// Fast weapon switch ready: skip flat-screen draw animation that rises from the floor
		static cvar_t *vr_weapon_skip_draw = NULL;
		if( !vr_weapon_skip_draw ) vr_weapon_skip_draw = gEngfuncs.pfnGetCvarPointer( "vr_weapon_skip_draw" );
		if( !vr_weapon_skip_draw || vr_weapon_skip_draw->value > 0.0f )
		{
			if( Q_stristr( pseqdesc->label, "draw" ) && pseqdesc->numframes > 1 )
			{
				f = (float)(pseqdesc->numframes - 1);
			}
		}

		// VR has no flat-screen equip animation: replace the draw/deploy sequence
		// with the resting idle pose and suppress the 0.2s transition blend.
		static cvar_t *vr_weapon_no_deploy = NULL;
		if( !vr_weapon_no_deploy ) vr_weapon_no_deploy = gEngfuncs.pfnGetCvarPointer( "vr_weapon_no_deploy" );
		if( vr_weapon_no_deploy && vr_weapon_no_deploy->value > 0.0f )
		{
			if( Q_stristr( pseqdesc->label, "draw" ) || Q_stristr( pseqdesc->label, "deploy" ))
			{
				int idle_seq = R_StudioFindSequence( m_pStudioHeader, "idle" );

				if( idle_seq >= 0 )
				{
					pseqdesc = (mstudioseqdesc_t *)((byte *)m_pStudioHeader + m_pStudioHeader->seqindex) + idle_seq;
					f = 0.0f;
				}
				else if( pseqdesc->numframes > 1 )
				{
					f = (float)(pseqdesc->numframes - 1);
				}

				static model_t *s_lastNoDeployModel = NULL;
				if( e->model && s_lastNoDeployModel != e->model )
				{
					s_lastNoDeployModel = e->model;
					gEngfuncs.Con_DPrintf( "[VR_WEAPON] No-deploy: %s equip animation replaced by idle pose\n", e->model->name );
				}

				skip_sequence_blend = true;
			}
			else if( Q_stristr( pseqdesc->label, "holster" ) && pseqdesc->numframes > 1 )
			{
				// Switching away: hold the first holster frame (ready pose) so
				// the old weapon stays in hand until it is swapped out instead
				// of lowering through the flat-screen animation.
				f = 0.0f;
				skip_sequence_blend = true;
			}
		}

		// Flat-screen melee swings (Crowbar attack1/2/3) rotate the whole
		// viewmodel through a canned arc. In VR the player's physical swing is
		// the animation, so freeze the weapon in its idle pose while the server
		// still resolves the damage.
		static cvar_t *vr_melee_suppress_attack_anim = NULL;
		if( !vr_melee_suppress_attack_anim ) vr_melee_suppress_attack_anim = gEngfuncs.pfnGetCvarPointer( "vr_melee_suppress_attack_anim" );

		if( vr_melee_suppress_attack_anim && vr_melee_suppress_attack_anim->value > 0.0f &&
		    e->model && Q_stristr( e->model->name, "crowbar" ) &&
		    Q_stristr( pseqdesc->label, "attack" ))
		{
			int idle_seq = R_StudioFindSequence( m_pStudioHeader, "idle" );

			if( idle_seq >= 0 )
			{
				pseqdesc = (mstudioseqdesc_t *)((byte *)m_pStudioHeader + m_pStudioHeader->seqindex) + idle_seq;
				f = 0.0f;
			}
			else
			{
				f = 0.0f;
			}

			static model_t *s_lastMeleeSuppressModel = NULL;
			if( s_lastMeleeSuppressModel != e->model )
			{
				s_lastMeleeSuppressModel = e->model;
				gEngfuncs.Con_DPrintf( "[VR_WEAPON] Melee attack animation suppressed: %s\n", e->model->name );
			}

			skip_sequence_blend = true;
		}
	}
#endif

	mstudioanim_t *panim = gEngfuncs.R_StudioGetAnim( m_pStudioHeader, RI.currentmodel, pseqdesc );
	R_StudioCalcRotations( e, pos, q, pseqdesc, panim, f );

	if( pseqdesc->numblends > 1 )
	{
		panim += m_pStudioHeader->numbones;
		R_StudioCalcRotations( e, pos2, q2, pseqdesc, panim, f );

		float dadt = R_StudioEstimateInterpolant( e );
		float s = (e->curstate.blending[0] * dadt + e->latched.prevblending[0] * (1.0f - dadt)) / 255.0f;

		R_StudioSlerpBones( m_pStudioHeader->numbones, q, pos, q2, pos2, s );

		if( pseqdesc->numblends == 4 )
		{
			panim += m_pStudioHeader->numbones;
			R_StudioCalcRotations( e, pos3, q3, pseqdesc, panim, f );

			panim += m_pStudioHeader->numbones;
			R_StudioCalcRotations( e, pos4, q4, pseqdesc, panim, f );

			s = (e->curstate.blending[0] * dadt + e->latched.prevblending[0] * (1.0f - dadt)) / 255.0f;
			R_StudioSlerpBones( m_pStudioHeader->numbones, q3, pos3, q4, pos4, s );

			s = (e->curstate.blending[1] * dadt + e->latched.prevblending[1] * (1.0f - dadt)) / 255.0f;
			R_StudioSlerpBones( m_pStudioHeader->numbones, q, pos, q3, pos3, s );
		}
	}

	if( !skip_sequence_blend && g_studio.interpolate && e->latched.sequencetime && ( e->latched.sequencetime + 0.2f > g_studio.time ) && ( e->latched.prevsequence < m_pStudioHeader->numseq ))
	{
		// blend from last sequence
		static vec3_t	pos1b[MAXSTUDIOBONES];
		static vec4_t	q1b[MAXSTUDIOBONES];

		pseqdesc = (mstudioseqdesc_t *)((byte *)m_pStudioHeader + m_pStudioHeader->seqindex) + e->latched.prevsequence;
		panim = gEngfuncs.R_StudioGetAnim( m_pStudioHeader, RI.currentmodel, pseqdesc );

		// clip prevframe
		R_StudioCalcRotations( e, pos1b, q1b, pseqdesc, panim, e->latched.prevframe );

		if( pseqdesc->numblends > 1 )
		{
			panim += m_pStudioHeader->numbones;
			R_StudioCalcRotations( e, pos2, q2, pseqdesc, panim, e->latched.prevframe );

			float s = (e->latched.prevseqblending[0]) / 255.0f;
			R_StudioSlerpBones( m_pStudioHeader->numbones, q1b, pos1b, q2, pos2, s );

			if( pseqdesc->numblends == 4 )
			{
				panim += m_pStudioHeader->numbones;
				R_StudioCalcRotations( e, pos3, q3, pseqdesc, panim, e->latched.prevframe );

				panim += m_pStudioHeader->numbones;
				R_StudioCalcRotations( e, pos4, q4, pseqdesc, panim, e->latched.prevframe );

				s = (e->latched.prevseqblending[0]) / 255.0f;
				R_StudioSlerpBones( m_pStudioHeader->numbones, q3, pos3, q4, pos4, s );

				s = (e->latched.prevseqblending[1]) / 255.0f;
				R_StudioSlerpBones( m_pStudioHeader->numbones, q1b, pos1b, q3, pos3, s );
			}
		}

		float s = 1.0f - ( g_studio.time - e->latched.sequencetime ) / 0.2f;
		R_StudioSlerpBones( m_pStudioHeader->numbones, q, pos, q1b, pos1b, s );
	}
	else
	{
		// store prevframe otherwise
		e->latched.prevframe = f;
	}

	mstudiobone_t *pbones = (mstudiobone_t *)((byte *)m_pStudioHeader + m_pStudioHeader->boneindex);

	// calc gait animation
	if( m_pPlayerInfo && m_pPlayerInfo->gaitsequence != 0 )
	{
		qboolean	copy_bones = true;

		if( m_pPlayerInfo->gaitsequence >= m_pStudioHeader->numseq )
			m_pPlayerInfo->gaitsequence = 0;

		pseqdesc = (mstudioseqdesc_t *)((byte *)m_pStudioHeader + m_pStudioHeader->seqindex) + m_pPlayerInfo->gaitsequence;

		panim = gEngfuncs.R_StudioGetAnim( m_pStudioHeader, RI.currentmodel, pseqdesc );
		R_StudioCalcRotations( e, pos2, q2, pseqdesc, panim, m_pPlayerInfo->gaitframe );

		for( int i = 0; i < m_pStudioHeader->numbones; i++ )
		{
			if( !Q_strcmp( pbones[i].name, "Bip01 Spine" ))
				copy_bones = false;
			else if( !Q_strcmp( pbones[pbones[i].parent].name, "Bip01 Pelvis" ))
				copy_bones = true;

			if( !copy_bones ) continue;

			VectorCopy( pos2[i], pos[i] );
			Vector4Copy( q2[i], q[i] );
		}
	}

#ifdef XASH_OPENXR
	// Apply procedural finger curling based on OpenXR analog axes (Trigger = Index, Grip = Middle/Ring/Pinky, Touch/Buttons = Thumb)
	if( (e == tr.viewent || e == &s_offhandEnt || e == &s_primaryHandEnt) && XR_IsActive() )
	{
		R_StudioApplyFingerCurling( e, m_pStudioHeader->numbones, pbones, q );
	}

	qboolean is_viewent = (e == tr.viewent);
	qboolean is_offhand_ent = (e == &s_offhandEnt);
	qboolean is_hand_ent = (is_offhand_ent || e == &s_primaryHandEnt);

	static cvar_t *vr_offhand_render = NULL;
	if( !vr_offhand_render ) vr_offhand_render = gEngfuncs.pfnGetCvarPointer( "vr_offhand_render" );
	qboolean offhand_enabled = (vr_offhand_render && vr_offhand_render->value > 0.0f);

	if( is_viewent )
	{
		s_viewmodel_has_offhand = false;
		for( int b = 0; b < m_pStudioHeader->numbones; b++ )
		{
			const char *bname = pbones[b].name;
			if( !Q_strcmp( bname, "Bip01 L Hand" ) ||
			    !Q_strcmp( bname, "Xbow biped L Hand" ) ||
			    !Q_strcmp( bname, "LeftArm" ) ||
			    (!Q_strcmp( bname, "Bone24" ) && e->model && Q_stristr( e->model->name, "9mmar" )) )
			{
				s_viewmodel_has_offhand = true;
				break;
			}
		}

		s_twohanded_active = R_VR_OffHandAttachedToWeapon();
	}
#endif

	for( int i = 0; i < m_pStudioHeader->numbones; i++ )
	{
#ifdef XASH_OPENXR

		// When off-hand presence is enabled and player is not two-handed gripping,
		// collapse any secondary arm/hand bones on the viewmodel so it does not render a duplicate 3rd hand.
		if( is_viewent && XR_IsActive() && offhand_enabled && !s_twohanded_active )
		{
			qboolean is_sec_arm = false;
			int p = i;
			while( p >= 0 )
			{
				const char *pname = pbones[p].name;
				if( !Q_strcmp( pname, "Bip01 L Arm" ) ||
				    !Q_strcmp( pname, "Xbow biped L Arm" ) ||
				    !Q_strcmp( pname, "LeftArm" ) ||
				    (!Q_strcmp( pname, "Bone19" ) && e->model && Q_stristr( e->model->name, "9mmar" )) )
				{
					is_sec_arm = true;
					break;
				}
				p = pbones[p].parent;
			}

			if( is_sec_arm )
			{
				// Collapse bone into parent origin with zero scale so vertices do not stretch to world origin (0,0,0)
				memset( g_studio.bonestransform[i], 0, sizeof( matrix3x4 ) );
				memset( g_studio.lighttransform[i], 0, sizeof( matrix3x4 ) );

				if( pbones[i].parent >= 0 )
				{
					g_studio.bonestransform[i][0][3] = g_studio.bonestransform[pbones[i].parent][0][3];
					g_studio.bonestransform[i][1][3] = g_studio.bonestransform[pbones[i].parent][1][3];
					g_studio.bonestransform[i][2][3] = g_studio.bonestransform[pbones[i].parent][2][3];

					g_studio.lighttransform[i][0][3] = g_studio.lighttransform[pbones[i].parent][0][3];
					g_studio.lighttransform[i][1][3] = g_studio.lighttransform[pbones[i].parent][1][3];
					g_studio.lighttransform[i][2][3] = g_studio.lighttransform[pbones[i].parent][2][3];
				}
				continue;
			}
		}
#endif
		matrix3x4 bonematrix;
		Matrix3x4_FromOriginQuat( bonematrix, q[i], pos[i] );

#ifdef XASH_OPENXR
		if( is_hand_ent )
		{
			// Standalone hand presence models (v_hand.mdl):
			// Concatenate cleanly from root with rotationmatrix (which is already
			// transformed to the 6DoF controller pose)
			if( pbones[i].parent == -1 )
			{
				Matrix3x4_ConcatTransforms( g_studio.bonestransform[i], g_studio.rotationmatrix, bonematrix );
				Matrix3x4_ConcatTransforms( g_studio.lighttransform[i], g_studio.rotationmatrix, bonematrix );
			}
			else
			{
				Matrix3x4_ConcatTransforms( g_studio.bonestransform[i], g_studio.bonestransform[pbones[i].parent], bonematrix );
				Matrix3x4_ConcatTransforms( g_studio.lighttransform[i], g_studio.lighttransform[pbones[i].parent], bonematrix );
			}
			continue;
		}
#endif

		if( pbones[i].parent == -1 )
		{
#ifdef XASH_OPENXR
			// In VR, 1998 flat viewmodels hide spare reload props (like Glock Box02 clip or Speedload Master)
			// offscreen at Z < -15 units. Collapse them to zero transform ONLY when not actively reloading
			// AND their translation is pushed offscreen (pos[i][2] < -15.0f).
			// Never collapse primary weapon meshes (such as RPG launcher or Tripmine chassis).
			if( is_viewent && XR_IsActive() && i > 0 && m_pStudioHeader->numseq > 0 )
			{
				qboolean has_children = false;

				// A legitimate second skeleton root (e.g. "Hands biped" in
				// v_rpg.mdl) owns child bones. Flat-screen spare props such as
				// clips and shell casings are always leaf roots.
				for( int c = 0; c < m_pStudioHeader->numbones; c++ )
				{
					if( pbones[c].parent == i )
					{
						has_children = true;
						break;
					}
				}

				int seq_idx = bound( 0, e->curstate.sequence, m_pStudioHeader->numseq - 1 );
				mstudioseqdesc_t *pseq = (mstudioseqdesc_t *)((byte *)m_pStudioHeader + m_pStudioHeader->seqindex) + seq_idx;
				qboolean is_reload = ( pseq && Q_stristr( pseq->label, "reload" ) != NULL );
				if( !has_children && !is_reload && pos[i][2] < -15.0f )
				{
					memset( g_studio.bonestransform[i], 0, sizeof( matrix3x4 ) );
					memset( g_studio.lighttransform[i], 0, sizeof( matrix3x4 ) );
					continue;
				}
			}
#endif
			Matrix3x4_ConcatTransforms( g_studio.bonestransform[i], g_studio.rotationmatrix, bonematrix );
			Matrix3x4_Copy( g_studio.lighttransform[i], g_studio.bonestransform[i] );

			// apply client-side effects to the transformation matrix
			R_StudioFxTransform( e, g_studio.bonestransform[i] );
		}
		else
		{
			Matrix3x4_ConcatTransforms( g_studio.bonestransform[i], g_studio.bonestransform[pbones[i].parent], bonematrix );
			Matrix3x4_ConcatTransforms( g_studio.lighttransform[i], g_studio.lighttransform[pbones[i].parent], bonematrix );
		}
	}
}

/*
====================
StudioSaveBones

====================
*/
static void R_StudioSaveBones( void )
{
	mstudiobone_t *pbones = (mstudiobone_t *)((byte *)m_pStudioHeader + m_pStudioHeader->boneindex);
	g_studio.cached_numbones = m_pStudioHeader->numbones;

	for( int i = 0; i < m_pStudioHeader->numbones; i++ )
	{
		Matrix3x4_Copy( g_studio.cached_bonestransform[i], g_studio.bonestransform[i] );
		Matrix3x4_Copy( g_studio.cached_lighttransform[i], g_studio.lighttransform[i] );
		Q_strncpy( g_studio.cached_bonenames[i], pbones[i].name, 32 );
	}
}

/*
====================
StudioBuildNormalTable

NOTE: m_pSubModel must be set
====================
*/
static void R_StudioBuildNormalTable( void )
{
	cl_entity_t	*e = RI.currententity;

	Assert( m_pSubModel != NULL );

	// reset chrome cache
	for( int i = 0; i < m_pStudioHeader->numbones; i++ )
		g_studio.chromeage[i] = 0;

	for( int i = 0; i < m_pSubModel->numverts; i++ )
		g_studio.normaltable[i] = -1;

	for( int j = 0; j < m_pSubModel->nummesh; j++ )
	{
		mstudiomesh_t *pmesh = (mstudiomesh_t *)((byte *)m_pStudioHeader + m_pSubModel->meshindex) + j;
		short *ptricmds = (short *)((byte *)m_pStudioHeader + pmesh->triindex);

		int i;
		while(( i = *( ptricmds++ )))
		{
			if( i < 0 ) i = -i;

			for( ; i > 0; i--, ptricmds += 4 )
			{
				if( g_studio.normaltable[ptricmds[0]] < 0 )
					g_studio.normaltable[ptricmds[0]] = ptricmds[1];
			}
		}
	}

	g_studio.chrome_origin[0] = cos( r_glowshellfreq->value * g_studio.time ) * 4000.0f;
	g_studio.chrome_origin[1] = sin( r_glowshellfreq->value * g_studio.time ) * 4000.0f;
	g_studio.chrome_origin[2] = cos( r_glowshellfreq->value * g_studio.time * 0.33f ) * 4000.0f;

	if( e->curstate.rendercolor.r || e->curstate.rendercolor.g || e->curstate.rendercolor.b )
		TriColor4ub( e->curstate.rendercolor.r, e->curstate.rendercolor.g, e->curstate.rendercolor.b, 255 );
	else TriColor4ub( 255, 255, 255, 255 );
}

/*
====================
StudioGenerateNormals

NOTE: m_pSubModel must be set
g_studio.verts must be computed
====================
*/
static void R_StudioGenerateNormals( void )
{
	Assert( m_pSubModel != NULL );

	for( int i = 0; i < m_pSubModel->numverts; i++ )
		VectorClear( g_studio.norms[i] );

	for( int j = 0; j < m_pSubModel->nummesh; j++ )
	{
		mstudiomesh_t *pmesh = (mstudiomesh_t *)((byte *)m_pStudioHeader + m_pSubModel->meshindex) + j;
		short *ptricmds = (short *)((byte *)m_pStudioHeader + pmesh->triindex);

		int i;
		while(( i = *( ptricmds++ )))
		{
			if( i < 0 )
			{
				i = -i;

				if( i > 2 )
				{
					vec3_t e0, e1, norm;
					int v0 = ptricmds[0]; ptricmds += 4;
					int v1 = ptricmds[0]; ptricmds += 4;

					for( i -= 2; i > 0; i--, ptricmds += 4 )
					{
						int v2 = ptricmds[0];

						VectorSubtract( g_studio.verts[v1], g_studio.verts[v0], e0 );
						VectorSubtract( g_studio.verts[v2], g_studio.verts[v0], e1 );
						CrossProduct( e1, e0, norm );

						VectorAdd( g_studio.norms[v0], norm, g_studio.norms[v0] );
						VectorAdd( g_studio.norms[v1], norm, g_studio.norms[v1] );
						VectorAdd( g_studio.norms[v2], norm, g_studio.norms[v2] );

						v1 = v2;
					}
				}
				else
				{
					ptricmds += i;
				}
			}
			else
			{
				if( i > 2 )
				{
					qboolean	odd = false;
					vec3_t e0, e1, norm;
					int v0 = ptricmds[0]; ptricmds += 4;
					int v1 = ptricmds[0]; ptricmds += 4;

					for( i -= 2; i > 0; i--, ptricmds += 4 )
					{
						int v2 = ptricmds[0];

						VectorSubtract( g_studio.verts[v1], g_studio.verts[v0], e0 );
						VectorSubtract( g_studio.verts[v2], g_studio.verts[v0], e1 );
						CrossProduct( e1, e0, norm );

						VectorAdd( g_studio.norms[v0], norm, g_studio.norms[v0] );
						VectorAdd( g_studio.norms[v1], norm, g_studio.norms[v1] );
						VectorAdd( g_studio.norms[v2], norm, g_studio.norms[v2] );

						if( odd ) v1 = v2;
						else v0 = v2;

						odd = !odd;
					}
				}
				else
				{
					ptricmds += i;
				}
			}
		}
	}

	for( int i = 0; i < m_pSubModel->numverts; i++ )
		VectorNormalize( g_studio.norms[i] );
}

/*
====================
StudioSetupChrome

====================
*/
static void R_StudioSetupChrome( float *pchrome, int bone, vec3_t normal )
{
	if( g_studio.chromeage[bone] != g_studio.framecount )
	{
		// calculate vectors from the viewer to the bone. This roughly adjusts for position
		vec3_t	chromeupvec;	// g_studio.chrome t vector in world reference frame
		vec3_t	chromerightvec;	// g_studio.chrome s vector in world reference frame
		vec3_t	tmp;		// vector pointing at bone in world reference frame

		VectorNegate( g_studio.chrome_origin, tmp );
		tmp[0] += g_studio.lighttransform[bone][0][3];
		tmp[1] += g_studio.lighttransform[bone][1][3];
		tmp[2] += g_studio.lighttransform[bone][2][3];

		VectorNormalize( tmp );
		CrossProduct( tmp, RI.vright, chromeupvec );
		VectorNormalize( chromeupvec );
		CrossProduct( chromeupvec, tmp, chromerightvec );
		VectorNormalize( chromerightvec );

		Matrix3x4_VectorIRotate( g_studio.lighttransform[bone], chromeupvec, g_studio.chromeup[bone] );
		Matrix3x4_VectorIRotate( g_studio.lighttransform[bone], chromerightvec, g_studio.chromeright[bone] );

		g_studio.chromeage[bone] = g_studio.framecount;
	}

	// calc s coord
	float n = DotProduct( normal, g_studio.chromeright[bone] );
	pchrome[0] = (n + 1.0f) * 32.0f;

	// calc t coord
	n = DotProduct( normal, g_studio.chromeup[bone] );
	pchrome[1] = (n + 1.0f) * 32.0f;
}

/*
====================
StudioCalcAttachments

====================
*/
static void R_StudioCalcAttachments( void )
{
	// calculate attachment points
	mstudioattachment_t *pAtt = (mstudioattachment_t *)((byte *)m_pStudioHeader + m_pStudioHeader->attachmentindex);

	for( int i = 0; i < Q_min( MAXSTUDIOATTACHMENTS, m_pStudioHeader->numattachments ); i++ )
	{
		Matrix3x4_VectorTransform( g_studio.lighttransform[pAtt[i].bone], pAtt[i].org, RI.currententity->attachment[i] );
	}

}

/*
===============
pfnStudioSetupModel

===============
*/
static void R_StudioSetupModel( int bodypart, void **ppbodypart, void **ppsubmodel )
{
	if( bodypart > m_pStudioHeader->numbodyparts )
		bodypart = 0;

	m_pBodyPart = (mstudiobodyparts_t *)((byte *)m_pStudioHeader + m_pStudioHeader->bodypartindex) + bodypart;

	int index = RI.currententity->curstate.body / m_pBodyPart->base;
	index = index % m_pBodyPart->nummodels;

	m_pSubModel = (mstudiomodel_t *)((byte *)m_pStudioHeader + m_pBodyPart->modelindex) + index;

	if( ppbodypart ) *ppbodypart = m_pBodyPart;
	if( ppsubmodel ) *ppsubmodel = m_pSubModel;
}

/*
===============
R_StudioCheckBBox

===============
*/
static int R_StudioCheckBBox( void )
{
	if( !RI.currententity || !RI.currentmodel )
		return false;

	return R_StudioComputeBBox( NULL );
}

/*
===============
pfnStudioEntityLight

===============
*/
static void R_StudioEntityLight( alight_t *lightinfo )
{
	float		lstrength[MAX_LOCALLIGHTS];
	cl_entity_t	*ent = RI.currententity;

	g_studio.numlocallights = 0;

	if( !ent || !r_dynamic->value )
		return;

	for( int i = 0; i < MAX_LOCALLIGHTS; i++ )
		lstrength[i] = 0;

	vec3_t origin;
	Matrix3x4_OriginFromMatrix( g_studio.rotationmatrix, origin );
	float dist2 = 1000000.0f;
	int k = 0;

	for( int lnum = 0; lnum < MAX_ELIGHTS; lnum++ )
	{
		dlight_t *el = &tr.elights[lnum];

		if( el->die < g_studio.time || el->radius <= 0.0f )
			continue;

		if(( el->key & 0xFFF ) == ent->index )
		{
			int	att = (el->key >> 12) & 0xF;

			if( att ) VectorCopy( ent->attachment[att], el->origin );
			else VectorCopy( ent->origin, el->origin );
		}

		vec3_t mid;
		VectorSubtract( origin, el->origin, mid );

		float f = DotProduct( mid, mid );
		float r2 = el->radius * el->radius;

		float minstrength;
		if( f > r2 ) minstrength = r2 / f;
		else minstrength = 1.0f;

		if( minstrength > 0.05f )
		{
			if( g_studio.numlocallights >= MAX_LOCALLIGHTS )
			{
				k = -1;
				for( int j = 0; j < g_studio.numlocallights; j++ )
				{
					if( lstrength[j] < dist2 && lstrength[j] < minstrength )
					{
						dist2 = lstrength[j];
						k = j;
					}
				}
			}
			else k = g_studio.numlocallights;

			if( k != -1 )
			{
				g_studio.locallightcolor[k][0] = LinearGammaTable( el->color.r << 2 );
				g_studio.locallightcolor[k][1] = LinearGammaTable( el->color.g << 2 );
				g_studio.locallightcolor[k][2] = LinearGammaTable( el->color.b << 2 );
				g_studio.locallightR2[k] = r2;
				g_studio.locallight[k] = el;
				lstrength[k] = minstrength;

				if( k >= g_studio.numlocallights )
					g_studio.numlocallights = k + 1;
			}
		}
	}
}

/*
===============
R_StudioSetupLighting

===============
*/
static void R_StudioSetupLighting( alight_t *plight )
{
	float	scale = 1.0f;

	if( !m_pStudioHeader || !plight )
		return;

	if( RI.currententity != NULL )
		scale = RI.currententity->curstate.scale;

	g_studio.ambientlight = plight->ambientlight;
	g_studio.shadelight = plight->shadelight;
	VectorCopy( plight->plightvec, g_studio.lightvec );

	for( int i = 0; i < m_pStudioHeader->numbones; i++ )
	{
		Matrix3x4_VectorIRotate( g_studio.lighttransform[i], plight->plightvec, g_studio.blightvec[i] );
		if( scale > 1.0f ) VectorNormalize( g_studio.blightvec[i] ); // in case model may be scaled
	}

	VectorCopy( plight->color, g_studio.lightcolor );
}

/*
===============
R_StudioLighting

===============
*/
static void R_StudioLighting( float *lv, int bone, int flags, vec3_t normal )
{
	if( FBitSet( flags, STUDIO_NF_FULLBRIGHT ))
	{
		*lv = 1.0f;
		return;
	}

	float illum = g_studio.ambientlight;

	if( FBitSet( flags, STUDIO_NF_FLATSHADE ))
	{
		illum += g_studio.shadelight * 0.8f;
	}
	else
	{
		float lightcos;
		if( bone != -1 ) lightcos = DotProduct( normal, g_studio.blightvec[bone] );
		else lightcos = DotProduct( normal, g_studio.lightvec ); // -1 colinear, 1 opposite
		if( lightcos > 1.0f ) lightcos = 1.0f;

		illum += g_studio.shadelight;

		float r = SHADE_LAMBERT;

 		// do modified hemispherical lighting
		if( r <= 1.0f )
		{
			r += 1.0f;
			lightcos = (( r - 1.0f ) - lightcos) / r;
			if( lightcos > 0.0f )
				illum += g_studio.shadelight * lightcos;
		}
		else
		{
			lightcos = (lightcos + ( r - 1.0f )) / r;
			if( lightcos > 0.0f )
				illum -= g_studio.shadelight * lightcos;
		}

		illum = Q_max( illum, 0.0f );
	}

	illum = Q_min( illum, 255.0f );

	*lv = LightToTexGamma( illum * 4 ) / 1023.0f;
}

/*
====================
R_LightLambert

====================
*/
static void R_LightLambert( vec4_t light[MAX_LOCALLIGHTS], const vec3_t normal, const vec3_t color, byte *out )
{
	if( !g_studio.numlocallights )
	{
		VectorScale( color, 255.0f, out );
		return;
	}

	vec3_t finalLight = { 0, 0, 0 };

	for( int i = 0; i < g_studio.numlocallights; i++ )
	{
		float r = DotProduct( normal, light[i] );
		if( likely( !tr.fFlipViewModel ))
			r = -r;

		if( r > 0.0f )
		{
			if( light[i][3] == 0.0f )
			{
				float r2 = DotProduct( light[i], light[i] );

				if( r2 > 0.0f )
					light[i][3] = g_studio.locallightR2[i] / ( r2 * sqrt( r2 ));
				else light[i][3] = 0.0001f;
			}

			float temp = r * light[i][3];

			vec3_t localLight;
			VectorAddScalar( g_studio.locallightcolor[i], temp, localLight );
			VectorAdd( finalLight, localLight, finalLight );
		}
	}

	if( !VectorIsNull( finalLight ))
	{
		for( int i = 0; i < 3; i++ )
		{
			float c = finalLight[i] + LinearGammaTable( color[i] * 1023.0f );

			if( c > 1023.0f )
				out[i] = 255;
			else
				out[i] = ScreenGammaTable( c ) >> 2;
		}
	}
	else
	{
		VectorScale( color, 255.0f, out );
	}
}

static void R_StudioSetColorArray( short *ptricmds, vec3_t *pstudionorms, byte *color )
{
	float	*lv = (float *)g_studio.lightvalues[ptricmds[1]];

	color[3] = tr.blend * 255;
	R_LightLambert( g_studio.lightpos[ptricmds[0]], pstudionorms[ptricmds[1]], lv, color );
}

static void R_StudioSetColorBegin( short *ptricmds, vec3_t *pstudionorms )
{
	rgba_t color;

	R_StudioSetColorArray( ptricmds, pstudionorms, color );
	pglColor4ubv( color );
}

/*
====================
R_LightStrength

====================
*/
static void R_LightStrength( int bone, vec3_t localpos, vec4_t light[MAX_LOCALLIGHTS] )
{
	if( g_studio.lightage[bone] != g_studio.framecount )
	{
		for( int i = 0; i < g_studio.numlocallights; i++ )
		{
			dlight_t *el = g_studio.locallight[i];
			Matrix3x4_VectorITransform( g_studio.lighttransform[bone], el->origin, g_studio.lightbonepos[bone][i] );
		}

		g_studio.lightage[bone] = g_studio.framecount;
	}

	for( int i = 0; i < g_studio.numlocallights; i++ )
	{
		VectorSubtract( localpos, g_studio.lightbonepos[bone][i], light[i] );
		light[i][3] = 0.0f;
	}
}

/*
===============
R_StudioSetupSkin

===============
*/
static void R_StudioSetupSkin( studiohdr_t *ptexturehdr, int index )
{
	mstudiotexture_t	*ptexture = NULL;

	if( FBitSet( g_nForceFaceFlags, STUDIO_NF_CHROME ))
		return;

	if( ptexturehdr == NULL )
		return;

	// NOTE: user may ignore to call StudioRemapColors and remap_info will be unavailable
	if( m_fDoRemap ) ptexture = gEngfuncs.CL_GetRemapInfoForEntity( RI.currententity )->ptexture;
	if( !ptexture ) ptexture = (mstudiotexture_t *)((byte *)ptexturehdr + ptexturehdr->textureindex); // fallback

	if( r_lightmap->value && !r_fullbright->value )
		GL_Bind( XASH_TEXTURE0, tr.whiteTexture );
	else GL_Bind( XASH_TEXTURE0, ptexture[index].index );
}

/*
===============
R_StudioGetTexture

Doesn't changes studio global state at all
===============
*/
mstudiotexture_t *R_StudioGetTexture( cl_entity_t *e )
{
	studiohdr_t *phdr;

	if(( phdr = gEngfuncs.Mod_Extradata( mod_studio, e->model )) == NULL )
		return NULL;

	studiohdr_t *thdr = m_pStudioHeader;
	if( !thdr ) return NULL;

	mstudiotexture_t *ptexture;
	if( m_fDoRemap ) ptexture = gEngfuncs.CL_GetRemapInfoForEntity( e )->ptexture;
	else ptexture = (mstudiotexture_t *)((byte *)thdr + thdr->textureindex);

	return ptexture;
}

static void R_StudioSetRenderamt( int iRenderamt )
{
	if( !RI.currententity ) return;

	RI.currententity->curstate.renderamt = iRenderamt;
	tr.blend = CL_FxBlend( RI.currententity ) / 255.0f;
}

/*
===============
R_StudioSetCullState

sets true for enable backculling (for left-hand viewmodel)
===============
*/
static void R_StudioSetCullState( int iCull )
{
	// This function intentionally does nothing
}

/*
===============
R_StudioRenderShadow

just a prefab for render shadow
===============
*/
static void R_StudioRenderShadow( int iSprite, float *p1, float *p2, float *p3, float *p4 )
{
	if( !p1 || !p2 || !p3 || !p4 )
		return;

	if( TriSpriteTexture( CL_ModelHandle( iSprite ), 0 ))
	{
		TriRenderMode( kRenderTransAlpha );
		TriColor4f( 0.0f, 0.0f, 0.0f, 1.0f );

		pglBegin( GL_QUADS );
			pglTexCoord2f( 0.0f, 0.0f );
			pglVertex3fv( p1 );
			pglTexCoord2f( 0.0f, 1.0f );
			pglVertex3fv( p2 );
			pglTexCoord2f( 1.0f, 1.0f );
			pglVertex3fv( p3 );
			pglTexCoord2f( 1.0f, 0.0f );
			pglVertex3fv( p4 );
		pglEnd();

		TriRenderMode( kRenderNormal );
	}
}

/*
===============
R_StudioMeshCompare

Sorting opaque entities by model type
===============
*/
static int R_StudioMeshCompare( const void *a, const void *b )
{
	if( FBitSet( ((const sortedmesh_t*)a)->flags, STUDIO_NF_ADDITIVE ))
		return 1;

	if( FBitSet( ((const sortedmesh_t*)a)->flags, STUDIO_NF_MASKED ))
		return -1;

	return 0;
}

/*
===============
R_StudioDrawNormalMesh

generic path
===============
*/
static void R_StudioDrawNormalMesh( short *ptricmds, vec3_t *pstudionorms, float s, float t )
{
	int	i;

	while(( i = *( ptricmds++ )))
	{
		if( i < 0 )
		{
			pglBegin( GL_TRIANGLE_FAN );
			i = -i;
		}
		else pglBegin( GL_TRIANGLE_STRIP );

		for( ; i > 0; i--, ptricmds += 4 )
		{
			R_StudioSetColorBegin( ptricmds, pstudionorms );

			pglTexCoord2f( ptricmds[2] * s, ptricmds[3] * t );
			pglVertex3fv( g_studio.verts[ptricmds[0]] );
		}

		pglEnd();
	}
}

/*
===============
R_StudioDrawNormalMesh

generic path
===============
*/
static void R_StudioDrawFloatMesh( short *ptricmds, vec3_t *pstudionorms )
{
	int	i;

	while(( i = *( ptricmds++ )))
	{
		if( i < 0 )
		{
			pglBegin( GL_TRIANGLE_FAN );
			i = -i;
		}
		else pglBegin( GL_TRIANGLE_STRIP );

		for( ; i > 0; i--, ptricmds += 4 )
		{
			R_StudioSetColorBegin( ptricmds, pstudionorms );
			pglTexCoord2f( HalfToFloat( ptricmds[2] ), HalfToFloat( ptricmds[3] ));
			pglVertex3fv( g_studio.verts[ptricmds[0]] );
		}

		pglEnd();
	}
}

/*
===============
R_StudioDrawNormalMesh

generic path
===============
*/
static void R_StudioDrawChromeMesh( short *ptricmds, vec3_t *pstudionorms, float s, float t, float scale )
{
	int	i;
	qboolean	glowShell = (scale > 0.0f) ? true : false;

	while(( i = *( ptricmds++ )))
	{
		if( i < 0 )
		{
			pglBegin( GL_TRIANGLE_FAN );
			i = -i;
		}
		else pglBegin( GL_TRIANGLE_STRIP );

		for( ; i > 0; i--, ptricmds += 4 )
		{
			int idx;
			if( glowShell )
			{
				color24 *clr = &RI.currententity->curstate.rendercolor;

				idx = g_studio.normaltable[ptricmds[0]];
				float *av = g_studio.verts[ptricmds[0]];
				float *lv = g_studio.norms[ptricmds[0]];
				vec3_t vert;
				VectorMA( av, scale, lv, vert );
				pglColor4ub( clr->r, clr->g, clr->b, 255 );
				pglTexCoord2f( g_studio.chrome[idx][0] * s, g_studio.chrome[idx][1] * t );
				pglVertex3fv( vert );
			}
			else
			{
				idx = ptricmds[1];
				R_StudioSetColorBegin( ptricmds, pstudionorms );
				pglTexCoord2f( g_studio.chrome[idx][0] * s, g_studio.chrome[idx][1] * t );
				pglVertex3fv( g_studio.verts[ptricmds[0]] );
			}
		}

		pglEnd();
	}
}


static int R_StudioBuildIndices( qboolean tri_strip, int vertexState )
{
	// build in indices
	if( vertexState++ < 3 )
	{
		g_studio.arrayelems[g_studio.numelems++] = g_studio.numverts;
	}
	else if( tri_strip )
	{
		// flip triangles between clockwise and counter clockwise
		if( vertexState & 1 )
		{
			// draw triangle [n-2 n-1 n]
			g_studio.arrayelems[g_studio.numelems++] = g_studio.numverts - 2;
			g_studio.arrayelems[g_studio.numelems++] = g_studio.numverts - 1;
			g_studio.arrayelems[g_studio.numelems++] = g_studio.numverts;
		}
		else
		{
			// draw triangle [n-1 n-2 n]
			g_studio.arrayelems[g_studio.numelems++] = g_studio.numverts - 1;
			g_studio.arrayelems[g_studio.numelems++] = g_studio.numverts - 2;
			g_studio.arrayelems[g_studio.numelems++] = g_studio.numverts;
		}
	}
	else
	{
		// draw triangle fan [0 n-1 n]
		g_studio.arrayelems[g_studio.numelems++] = g_studio.numverts - ( vertexState - 1 );
		g_studio.arrayelems[g_studio.numelems++] = g_studio.numverts - 1;
		g_studio.arrayelems[g_studio.numelems++] = g_studio.numverts;
	}

	return vertexState;
}

/*
===============
R_StudioDrawNormalMesh

generic path
===============
*/
static void R_StudioBuildArrayNormalMesh( short *ptricmds, vec3_t *pstudionorms, float s, float t )
{
	int	i;

	while(( i = *( ptricmds++ )))
	{
		int vertexState = 0;
		qboolean tri_strip = true;

		if( i < 0 )
		{
			tri_strip = false;
			i = -i;
		}

		for( ; i > 0; i--, ptricmds += 4 )
		{
			GLubyte *cl = g_studio.arraycolor[g_studio.numverts];

			vertexState = R_StudioBuildIndices( tri_strip, vertexState );

			R_StudioSetColorArray( ptricmds, pstudionorms, cl );

			g_studio.arraycoord[g_studio.numverts][0] = ptricmds[2] * s;
			g_studio.arraycoord[g_studio.numverts][1] = ptricmds[3] * t;

			VectorCopy( g_studio.verts[ptricmds[0]], g_studio.arrayverts[g_studio.numverts] );
			g_studio.numverts++;
		}
	}
}

/*
===============
R_StudioDrawNormalMesh

generic path
===============
*/
static void R_StudioBuildArrayFloatMesh( short *ptricmds, vec3_t *pstudionorms )
{
	int	i;

	while(( i = *( ptricmds++ )))
	{
		int vertexState = 0;
		qboolean tri_strip = true;

		if( i < 0 )
		{
			tri_strip = false;
			i = -i;
		}

		for( ; i > 0; i--, ptricmds += 4 )
		{
			GLubyte *cl = g_studio.arraycolor[g_studio.numverts];

			vertexState = R_StudioBuildIndices( tri_strip, vertexState );

			R_StudioSetColorArray( ptricmds, pstudionorms, cl );

			g_studio.arraycoord[g_studio.numverts][0] = HalfToFloat( ptricmds[2] );
			g_studio.arraycoord[g_studio.numverts][1] = HalfToFloat( ptricmds[3] );

			VectorCopy( g_studio.verts[ptricmds[0]], g_studio.arrayverts[g_studio.numverts] );
			g_studio.numverts++;
		}
	}
}

/*
===============
R_StudioDrawNormalMesh

generic path
===============
*/
static void R_StudioBuildArrayChromeMesh( short *ptricmds, vec3_t *pstudionorms, float s, float t, float scale )
{
	int	i;
	qboolean	glowShell = (scale > 0.0f) ? true : false;

	while(( i = *( ptricmds++ )))
	{
		int vertexState = 0;
		qboolean tri_strip = true;

		if( i < 0 )
		{
			tri_strip = false;
			i = -i;
		}

		for( ; i > 0; i--, ptricmds += 4 )
		{
			GLubyte *cl = g_studio.arraycolor[g_studio.numverts];

			vertexState = R_StudioBuildIndices( tri_strip, vertexState );

			int idx;
			if( glowShell )
			{
				idx = g_studio.normaltable[ptricmds[0]];
				float *av = g_studio.verts[ptricmds[0]];
				float *lv = g_studio.norms[ptricmds[0]];

				cl[0] = RI.currententity->curstate.rendercolor.r;
				cl[1] = RI.currententity->curstate.rendercolor.g;
				cl[2] = RI.currententity->curstate.rendercolor.b;
				cl[3] = 255;

				vec3_t vert;
				VectorMA( av, scale, lv, vert );
				VectorCopy( vert, g_studio.arrayverts[g_studio.numverts] );
			}
			else
			{
				idx = ptricmds[1];
				R_StudioSetColorArray( ptricmds, pstudionorms, cl );

				VectorCopy( g_studio.verts[ptricmds[0]], g_studio.arrayverts[g_studio.numverts] );
			}

			g_studio.arraycoord[g_studio.numverts][0] = g_studio.chrome[idx][0] * s;
			g_studio.arraycoord[g_studio.numverts][1] = g_studio.chrome[idx][1] * t;

			g_studio.numverts++;
		}
	}
}

static void R_StudioDrawArrays( uint startverts, uint startelems )
{
	if( g_studio.numelems == startelems )
		return;

	pglEnableClientState( GL_VERTEX_ARRAY );
	pglVertexPointer( 3, GL_FLOAT, 12, g_studio.arrayverts );

	pglEnableClientState( GL_TEXTURE_COORD_ARRAY );
	pglTexCoordPointer( 2, GL_FLOAT, 0, g_studio.arraycoord );

	if( !( g_nForceFaceFlags & STUDIO_NF_CHROME ) )
	{
		pglEnableClientState( GL_COLOR_ARRAY );
		pglColorPointer( 4, GL_UNSIGNED_BYTE, 0, g_studio.arraycolor );
	}

	GL_DrawRangeElements( GL_TRIANGLES, startverts, g_studio.numverts - 1, g_studio.numelems - startelems, GL_UNSIGNED_SHORT, &g_studio.arrayelems[startelems] );
	pglDisableClientState( GL_VERTEX_ARRAY );
	pglDisableClientState( GL_TEXTURE_COORD_ARRAY );
	if( !( g_nForceFaceFlags & STUDIO_NF_CHROME ) )
		pglDisableClientState( GL_COLOR_ARRAY );
}

/*
===============
R_StudioSubmitMesh

===============
*/
static void R_StudioSubmitMesh( short *ptricmds, vec3_t *pstudionorms, float s, float t, float shellscale, int tesslevel )
{
	if( tesslevel > 0 )
	{
		// R_StudioDrawTruformMesh( ptricmds, pstudionorms, s, t, shellscale, tesslevel );
	}
	else if( r_studio_drawelements.value )
	{
		uint startArrayVerts = g_studio.numverts;
		uint startArrayElems = g_studio.numelems;

		if( FBitSet( g_nFaceFlags, STUDIO_NF_CHROME ))
			R_StudioBuildArrayChromeMesh( ptricmds, pstudionorms, s, t, shellscale );
		else if( FBitSet( g_nFaceFlags, STUDIO_NF_UV_COORDS ))
			R_StudioBuildArrayFloatMesh( ptricmds, pstudionorms );
		else
			R_StudioBuildArrayNormalMesh( ptricmds, pstudionorms, s, t );

		R_StudioDrawArrays( startArrayVerts, startArrayElems );
	}
	else
	{
		if( FBitSet( g_nFaceFlags, STUDIO_NF_CHROME ))
			R_StudioDrawChromeMesh( ptricmds, pstudionorms, s, t, shellscale );
		else if( FBitSet( g_nFaceFlags, STUDIO_NF_UV_COORDS ))
			R_StudioDrawFloatMesh( ptricmds, pstudionorms );
		else
			R_StudioDrawNormalMesh( ptricmds, pstudionorms, s, t );
	}
}

/*
===============
R_StudioDrawPoints

===============
*/
static void R_StudioDrawPoints( void )
{
	float		shellscale = 0.0f;
	qboolean		need_sort = false;

	if( !m_pStudioHeader ) return;


	g_studio.numverts = g_studio.numelems = 0;

	int m_skinnum = RI.currententity->curstate.skin;
	mstudiotexture_t *ptexture = (mstudiotexture_t *)((byte *)m_pStudioHeader + m_pStudioHeader->textureindex);
	byte *pvertbone = ((byte *)m_pStudioHeader + m_pSubModel->vertinfoindex);
	byte *pnormbone = ((byte *)m_pStudioHeader + m_pSubModel->norminfoindex);

	mstudiomesh_t *pmesh = (mstudiomesh_t *)((byte *)m_pStudioHeader + m_pSubModel->meshindex);
	vec3_t *pstudioverts = (vec3_t *)((byte *)m_pStudioHeader + m_pSubModel->vertindex);
	vec3_t *pstudionorms = (vec3_t *)((byte *)m_pStudioHeader + m_pSubModel->normindex);

	short *pskinref = (short *)((byte *)m_pStudioHeader + m_pStudioHeader->skinindex);
	if( m_skinnum > 0 && m_skinnum < m_pStudioHeader->numskinfamilies )
		pskinref += (m_skinnum * m_pStudioHeader->numskinref);

	const int numverts = m_pSubModel->numverts;
	const int numnorms = m_pSubModel->numnorms;

	if( FBitSet( m_pStudioHeader->flags, STUDIO_HAS_BONEWEIGHTS ) && m_pSubModel->blendvertinfoindex != 0 && m_pSubModel->blendnorminfoindex != 0 )
	{
		mstudioboneweight_t	*pvertweight = (mstudioboneweight_t *)((byte *)m_pStudioHeader + m_pSubModel->blendvertinfoindex);
		mstudioboneweight_t	*pnormweight = (mstudioboneweight_t *)((byte *)m_pStudioHeader + m_pSubModel->blendnorminfoindex);
		matrix3x4		skinMat;

		for( int i = 0; i < numverts; i++ )
		{
			R_StudioComputeSkinMatrix( &pvertweight[i], skinMat );
			Matrix3x4_VectorTransform( skinMat, pstudioverts[i], g_studio.verts[i] );
			R_LightStrength( pvertbone[i], pstudioverts[i], g_studio.lightpos[i] );
		}

		for( int i = 0; i < numnorms; i++ )
		{
			R_StudioComputeSkinMatrix( &pnormweight[i], skinMat );
			Matrix3x4_VectorRotate( skinMat, pstudionorms[i], g_studio.norms[i] );
		}
	}
	else
	{
		for( int i = 0; i < numverts; i++ )
			Matrix3x4_VectorTransform( g_studio.bonestransform[pvertbone[i]], pstudioverts[i], g_studio.verts[i] );

		for( int i = 0; i < numverts; i++ )
			R_LightStrength( pvertbone[i], pstudioverts[i], g_studio.lightpos[i] );
	}

	// generate shared normals for properly scaling glowing shell
	if( RI.currententity->curstate.renderfx == kRenderFxGlowShell )
	{
		float factor = (1.0f / 128.0f);
		shellscale = Q_max( factor, RI.currententity->curstate.renderamt * factor );
		R_StudioBuildNormalTable();
		R_StudioGenerateNormals();
	}

	int k = 0;
	for( int j = 0; j < m_pSubModel->nummesh; j++ )
	{
		g_nFaceFlags = ptexture[pskinref[pmesh[j].skinref]].flags | g_nForceFaceFlags;

		// fill in sortedmesh info
		g_studio.meshes[j].flags = g_nFaceFlags;
		g_studio.meshes[j].mesh = &pmesh[j];

		if( FBitSet( g_nFaceFlags, STUDIO_NF_MASKED|STUDIO_NF_ADDITIVE ))
			need_sort = true;

		if( RI.currententity->curstate.rendermode == kRenderTransAdd )
		{
			for( int i = 0; i < pmesh[j].numnorms; i++, k++, pstudionorms++, pnormbone++ )
			{
				if( FBitSet( g_nFaceFlags, STUDIO_NF_CHROME ))
					R_StudioSetupChrome( g_studio.chrome[k], *pnormbone, (float *)pstudionorms );
				VectorSet( g_studio.lightvalues[k], tr.blend, tr.blend, tr.blend );
			}
		}
		else
		{
			for( int i = 0; i < pmesh[j].numnorms; i++, k++, pstudionorms++, pnormbone++ )
			{
				float lv_tmp;
				if( FBitSet( m_pStudioHeader->flags, STUDIO_HAS_BONEWEIGHTS ))
					R_StudioLighting( &lv_tmp, -1, g_nFaceFlags, g_studio.norms[k] );
				else R_StudioLighting( &lv_tmp, *pnormbone, g_nFaceFlags, (float *)pstudionorms );

				if( FBitSet( g_nFaceFlags, STUDIO_NF_CHROME ))
					R_StudioSetupChrome( g_studio.chrome[k], *pnormbone, (float *)pstudionorms );
				VectorScale( g_studio.lightcolor, lv_tmp, g_studio.lightvalues[k] );
			}
		}
	}

	if( r_studio_sort_textures.value && need_sort )
	{
		// resort opaque and translucent meshes draw order
		qsort( g_studio.meshes, m_pSubModel->nummesh, sizeof( sortedmesh_t ), R_StudioMeshCompare );
	}

	// NOTE: rewind normals at start
	pstudionorms = (vec3_t *)((byte *)m_pStudioHeader + m_pSubModel->normindex);

	// backface culling for left-handed weapons
	//
	// there is a bug in GoldSrc that sets backface culling to GL_FRONT
	// but doesn't enable OpenGL GL_CULL_FACE. This allows mod developers to disable
	// backface culling through TriAPI call
	//
	// see https://github.com/FWGS/xash3d-fwgs/issues/2517
	if( RI.currententity == &s_offhandEnt || RI.currententity == &s_primaryHandEnt )
	{
		// The standalone hands carry a dark inner liner; render both faces so
		// the glove/sleeve interior is not culled away.
		tr.fFlipViewModel = false;
		GL_Cull( GL_NONE );
	}
	else if( glState.faceCull != GL_NONE )
	{
		if( R_AllowFlipViewModel( RI.currententity ))
		{
			tr.fFlipViewModel = true;
			GL_Cull( GL_NONE );
		}
		else
		{
			tr.fFlipViewModel = false;
			GL_Cull( GL_FRONT );
		}
	}

	for( int j = 0; j < m_pSubModel->nummesh; j++ )
	{
		float	oldblend = tr.blend;

		pmesh = g_studio.meshes[j].mesh;
		short *ptricmds = (short *)((byte *)m_pStudioHeader + pmesh->triindex);

#ifdef XASH_OPENXR
		// vr_hide_arms only applies to the weapon viewmodel: it strips the
		// baked glove/sleeve so the standalone hand model is used instead.
		// The standalone hand entities must never be filtered, or they would
		// hide their own glove/sleeve textures.
		if( RI.currententity == tr.viewent && XR_IsActive() )
		{
			static cvar_t *vr_hide_arms = NULL;
			if( !vr_hide_arms ) vr_hide_arms = gEngfuncs.pfnGetCvarPointer( "vr_hide_arms" );

			float hide_mode = vr_hide_arms ? vr_hide_arms->value : 1.0f;
			if( hide_mode > 0.0f )
			{
				const char *texname = ptexture[pskinref[pmesh->skinref]].name;

				// Mode 1: Hide the rigid flat forearm, sleeve, cuffs, severed shoulders, and player suit arm chrome
				if( Q_stristr( texname, "sleeve" ) ||
				    Q_stristr( texname, "forearm" ) ||
				    Q_stristr( texname, "cuff" ) ||
				    Q_stristr( texname, "arm1" ) ||
				    Q_stristr( texname, "player_arm" ) ||
				    Q_stristr( texname, "player_chrome" ) )
				{
					continue; // Hide flat sleeve/forearm/shoulders
				}

				// Mode 2: Also hide the 3D hand and glove meshes
				if( hide_mode >= 2.0f )
				{
					if( Q_stristr( texname, "glove" ) ||
					    Q_stristr( texname, "knuckle" ) ||
					    Q_stristr( texname, "handpak" ) ||
					    (Q_stristr( texname, "hand" ) && !Q_stristr( texname, "handle" )) )
					{
						continue; // Hide hand/glove
					}
				}
			}
		}
#endif

		g_nFaceFlags = ptexture[pskinref[pmesh->skinref]].flags | g_nForceFaceFlags;

		float s = 1.0f / (float)ptexture[pskinref[pmesh->skinref]].width;
		float t = 1.0f / (float)ptexture[pskinref[pmesh->skinref]].height;

		if( FBitSet( g_nFaceFlags, STUDIO_NF_MASKED ))
		{
			pglEnable( GL_ALPHA_TEST );
			pglAlphaFunc( GL_GREATER, 0.5f );
			pglDepthMask( GL_TRUE );
			if( R_ModelOpaque( RI.currententity->curstate.rendermode ))
				tr.blend = 1.0f;
		}
		else if( FBitSet( g_nFaceFlags, STUDIO_NF_ADDITIVE ))
		{
			if( R_ModelOpaque( RI.currententity->curstate.rendermode ))
			{
				pglBlendFunc( GL_ONE, GL_ONE );
				pglDepthMask( GL_FALSE );
				pglEnable( GL_BLEND );
				R_AllowFog( false );
			}
			else pglBlendFunc( GL_SRC_ALPHA, GL_ONE );
		}

		R_StudioSetupSkin( m_pStudioHeader, pskinref[pmesh->skinref] );

		R_StudioSubmitMesh( ptricmds, pstudionorms, s, t, shellscale, 0 );

		if( FBitSet( g_nFaceFlags, STUDIO_NF_MASKED ))
		{
			pglAlphaFunc( GL_GREATER, DEFAULT_ALPHATEST );
			pglDisable( GL_ALPHA_TEST );
		}
		else if( FBitSet( g_nFaceFlags, STUDIO_NF_ADDITIVE ) && R_ModelOpaque( RI.currententity->curstate.rendermode ))
		{
			pglDepthMask( GL_TRUE );
			pglDisable( GL_BLEND );
			R_AllowFog( true );
		}

		r_stats.c_studio_polys += pmesh->numtris;
		tr.blend = oldblend;
	}
}

/*
===============
R_StudioDrawHulls

===============
*/
static void R_StudioDrawHulls( void )
{
	float alpha = ( r_drawentities->value == 4 ) ? 0.5f : 1.0f;

	GL_Bind( XASH_TEXTURE0, tr.whiteTexture );
	pglTexEnvf( GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE );

	for( int i = 0; i < m_pStudioHeader->numhitboxes; i++ )
	{
		mstudiobbox_t	*pbbox = (mstudiobbox_t *)((byte *)m_pStudioHeader + m_pStudioHeader->hitboxindex);
		vec3_t		tmp, p[8];

		for( int j = 0; j < 8; j++ )
		{
			tmp[0] = (j & 1) ? pbbox[i].bbmin[0] : pbbox[i].bbmax[0];
			tmp[1] = (j & 2) ? pbbox[i].bbmin[1] : pbbox[i].bbmax[1];
			tmp[2] = (j & 4) ? pbbox[i].bbmin[2] : pbbox[i].bbmax[2];

			Matrix3x4_VectorTransform( g_studio.bonestransform[pbbox[i].bone], tmp, p[j] );
		}

		int j = (pbbox[i].group % 8);

		TriBegin( TRI_QUADS );
		TriColor4f( hullcolor[j][0], hullcolor[j][1], hullcolor[j][2], alpha );

		for( j = 0; j < 6; j++ )
		{
			float lv;
			VectorClear( tmp );
			tmp[j % 3] = (j < 3) ? 1.0f : -1.0f;
			R_StudioLighting( &lv, pbbox[i].bone, 0, tmp );

			TriBrightness( lv );
			TriVertex3fv( p[boxpnt[j][0]] );
			TriVertex3fv( p[boxpnt[j][1]] );
			TriVertex3fv( p[boxpnt[j][2]] );
			TriVertex3fv( p[boxpnt[j][3]] );
		}
		TriEnd();
	}
}

/*
===============
R_StudioDrawAbsBBox

===============
*/
static void R_StudioDrawAbsBBox( void )
{
	vec3_t	p[8], tmp;

	// looks ugly, skip
	if( RI.currententity == tr.viewent )
		return;

	if( !R_StudioComputeBBox( p ))
		return;

	GL_Bind( XASH_TEXTURE0, tr.whiteTexture );
	TriColor4f( 0.5f, 0.5f, 1.0f, 0.5f );
	TriRenderMode( kRenderTransAdd );

	TriBegin( TRI_QUADS );
	for( int i = 0; i < 6; i++ )
	{
		float lv;
		VectorClear( tmp );
		tmp[i % 3] = (i < 3) ? 1.0f : -1.0f;
		R_StudioLighting( &lv, -1, 0, tmp );

		TriBrightness( lv );
		TriVertex3fv( p[boxpnt[i][0]] );
		TriVertex3fv( p[boxpnt[i][1]] );
		TriVertex3fv( p[boxpnt[i][2]] );
		TriVertex3fv( p[boxpnt[i][3]] );
	}
	TriEnd();
	TriRenderMode( kRenderNormal );
}

/*
===============
R_StudioDrawBones

===============
*/
static void R_StudioDrawBones( void )
{
	mstudiobone_t	*pbones = (mstudiobone_t *) ((byte *)m_pStudioHeader + m_pStudioHeader->boneindex);
	vec3_t		point;

	pglDisable( GL_TEXTURE_2D );

	for( int i = 0; i < m_pStudioHeader->numbones; i++ )
	{
		if( pbones[i].parent >= 0 )
		{
			pglPointSize( 3.0f );
			pglColor3f( 1, 0.7f, 0 );
			pglBegin( GL_LINES );

			Matrix3x4_OriginFromMatrix( g_studio.bonestransform[pbones[i].parent], point );
			pglVertex3fv( point );
			Matrix3x4_OriginFromMatrix( g_studio.bonestransform[i], point );
			pglVertex3fv( point );

			pglEnd();

			pglColor3f( 0, 0, 0.8f );
			pglBegin( GL_POINTS );
			if( pbones[pbones[i].parent].parent != -1 )
			{
				Matrix3x4_OriginFromMatrix( g_studio.bonestransform[pbones[i].parent], point );
				pglVertex3fv( point );
			}
			Matrix3x4_OriginFromMatrix( g_studio.bonestransform[i], point );
			pglVertex3fv( point );
			pglEnd();
		}
		else
		{
			// draw parent bone node
			pglPointSize( 5.0f );
			pglColor3f( 0.8f, 0, 0 );
			pglBegin( GL_POINTS );
			Matrix3x4_OriginFromMatrix( g_studio.bonestransform[i], point );
			pglVertex3fv( point );
			pglEnd();
		}
	}

	pglPointSize( 1.0f );
	pglEnable( GL_TEXTURE_2D );
}

static void R_StudioDrawAttachments( void )
{
	pglDisable( GL_TEXTURE_2D );
	pglDisable( GL_DEPTH_TEST );

	for( int i = 0; i < m_pStudioHeader->numattachments; i++ )
	{
		vec3_t		v[4];

		mstudioattachment_t *pattachments = (mstudioattachment_t *)((byte *)m_pStudioHeader + m_pStudioHeader->attachmentindex);
		Matrix3x4_VectorTransform( g_studio.bonestransform[pattachments[i].bone], pattachments[i].org, v[0] );
		Matrix3x4_VectorTransform( g_studio.bonestransform[pattachments[i].bone], pattachments[i].vectors[0], v[1] );
		Matrix3x4_VectorTransform( g_studio.bonestransform[pattachments[i].bone], pattachments[i].vectors[1], v[2] );
		Matrix3x4_VectorTransform( g_studio.bonestransform[pattachments[i].bone], pattachments[i].vectors[2], v[3] );

		pglBegin( GL_LINES );
		pglColor3f( 1, 0, 0 );
		pglVertex3fv( v[0] );
		pglColor3f( 1, 1, 1 );
		pglVertex3fv (v[1] );
		pglColor3f( 1, 0, 0 );
		pglVertex3fv (v[0] );
		pglColor3f( 1, 1, 1 );
		pglVertex3fv (v[2] );
		pglColor3f( 1, 0, 0 );
		pglVertex3fv (v[0] );
		pglColor3f( 1, 1, 1 );
		pglVertex3fv( v[3] );
		pglEnd();

		pglPointSize( 5.0f );
		pglColor3f( 0, 1, 0 );
		pglBegin( GL_POINTS );
		pglVertex3fv( v[0] );
		pglEnd();
		pglPointSize( 1.0f );
	}

	pglEnable( GL_TEXTURE_2D );
	pglEnable( GL_DEPTH_TEST );
}

/*
===============
R_StudioSetRemapColors

===============
*/
static void R_StudioSetRemapColors( int newTop, int newBottom )
{
	if( gEngfuncs.CL_EntitySetRemapColors( RI.currententity, RI.currentmodel, newTop, newBottom ))
		m_fDoRemap = true;
}

void R_StudioResetPlayerModels( void )
{
	memset( g_studio.player_models, 0, sizeof( g_studio.player_models ));
}

/*
===============
R_StudioSetupPlayerModel

===============
*/
static model_t *R_StudioSetupPlayerModel( int index )
{
	player_info_t  *info = gEngfuncs.pfnPlayerInfo( index );

	if( index < 0 || index >= gp_cl->maxclients )
		return NULL;

	player_model_t *state = &g_studio.player_models[index];

	// g-cont: force for "dev-mode", non-local games and menu preview
	if(( gpGlobals->developer || !ENGINE_GET_PARM( PARM_SINGLEPLAYER_GAME ) || !FBitSet( RI.rvp.flags, RF_DRAW_WORLD ) ) && info->model[0] )
	{
		if( Q_strcmp( state->name, info->model ))
		{
			Q_strncpy( state->name, info->model, sizeof( state->name ));
			state->name[sizeof( state->name ) - 1] = 0;

			Q_snprintf( state->modelname, sizeof( state->modelname ), "models/player/%s/%s.mdl", info->model, info->model );

			if( gEngfuncs.fsapi->FileExists( state->modelname, false ))
				state->model = gEngfuncs.Mod_ForName( state->modelname, false, true );
			else
				state->model = NULL;

			if( !state->model )
				state->model = RI.currententity->model;
		}
	}
	else
	{
		if( state->model != RI.currententity->model )
			state->model = RI.currententity->model;
		state->name[0] = 0;
	}

	return state->model;
}

/*
================
R_GetEntityRenderMode

check for texture flags
================
*/
int R_GetEntityRenderMode( cl_entity_t *ent )
{
	model_t *model = NULL;

	cl_entity_t *oldent = RI.currententity;
	RI.currententity = ent;

	if( ent->player ) // check it for real playermodel
		model = R_StudioSetupPlayerModel( ent->curstate.number - 1 );

	if( !model )
		model = ent->model;

	RI.currententity = oldent;

	studiohdr_t *phdr;
	if(( phdr = gEngfuncs.Mod_Extradata( mod_studio, model )) == NULL )
	{
		if( R_ModelOpaque( ent->curstate.rendermode ))
		{
			// forcing to choose right sorting type
			if(( model && model->type == mod_brush ) && FBitSet( model->flags, MODEL_TRANSPARENT ))
				return kRenderTransAlpha;
		}
		return ent->curstate.rendermode;
	}
	mstudiotexture_t *ptexture = (mstudiotexture_t *)((byte *)phdr + phdr->textureindex);

	int opaque = 0, trans = 0;
	for( int i = 0; i < phdr->numtextures; i++, ptexture++ )
	{
		// ignore chrome & additive it's just a specular-like effect
		if( FBitSet( ptexture->flags, STUDIO_NF_ADDITIVE ) && !FBitSet( ptexture->flags, STUDIO_NF_CHROME ))
			trans++;
		else opaque++;
	}

	// if model is more additive than opaque
	if( trans > opaque )
		return kRenderTransAdd;
	return ent->curstate.rendermode;
}

/*
===============
R_StudioClientEvents

===============
*/
static void R_StudioClientEvents( void )
{
	cl_entity_t	*e = RI.currententity;

	if( g_studio.frametime == 0.0 )
		return; // gamepaused

	// fill attachments with interpolated origin
	if( m_pStudioHeader->numattachments <= 0 )
	{
		Matrix3x4_OriginFromMatrix( g_studio.rotationmatrix, e->attachment[0] );
		Matrix3x4_OriginFromMatrix( g_studio.rotationmatrix, e->attachment[1] );
		Matrix3x4_OriginFromMatrix( g_studio.rotationmatrix, e->attachment[2] );
		Matrix3x4_OriginFromMatrix( g_studio.rotationmatrix, e->attachment[3] );

#ifdef XASH_OPENXR
		// If this is the VR viewmodel and lacks authored attachments, synthesize
		// a virtual muzzle attachment at the forward physical barrel tip.
		if( e == tr.viewent && XR_IsActive() )
		{
			vec3_t fwd, up;
			// In GoldSrc rotation matrices, column 0 is Forward and column 2 is Up
			fwd[0] = g_studio.rotationmatrix[0][0];
			fwd[1] = g_studio.rotationmatrix[1][0];
			fwd[2] = g_studio.rotationmatrix[2][0];
			up[0]  = g_studio.rotationmatrix[0][2];
			up[1]  = g_studio.rotationmatrix[1][2];
			up[2]  = g_studio.rotationmatrix[2][2];

			float barrel_len = m_pStudioHeader->bbmax[0];
			if( barrel_len < 8.0f || barrel_len > 45.0f )
			{
				float total_span = m_pStudioHeader->bbmax[0] - m_pStudioHeader->bbmin[0];
				if( total_span > 12.0f && total_span < 60.0f )
					barrel_len = total_span * 0.70f;
				else
					barrel_len = 18.0f; // Sane GoldSrc weapon default length
			}

			// Project virtual muzzle along the physical barrel axis
			VectorMA( e->attachment[0], barrel_len, fwd, e->attachment[0] );
			VectorMA( e->attachment[0], 1.5f, up, e->attachment[0] );
		}
#endif
	}

	if( FBitSet( e->curstate.effects, EF_MUZZLEFLASH ))
	{
		dlight_t	*el = gEngfuncs.CL_AllocElight( 0 );

		ClearBits( e->curstate.effects, EF_MUZZLEFLASH );
		VectorCopy( e->attachment[0], el->origin );
		el->die = gp_cl->time + 0.05f;
		el->color.r = 255;
		el->color.g = 192;
		el->color.b = 64;
		el->decay = 320;
		el->radius = 24;
	}

	int sequence = bound( 0, e->curstate.sequence, m_pStudioHeader->numseq - 1 );
	mstudioseqdesc_t *pseqdesc = (mstudioseqdesc_t *)((byte *)m_pStudioHeader + m_pStudioHeader->seqindex) + sequence;

	// no events for this animation
	if( pseqdesc->numevents == 0 )
		return;

	float end = R_StudioEstimateFrame( e, pseqdesc, g_studio.time );
	float start = end - e->curstate.framerate * gp_host->frametime * pseqdesc->fps;
	mstudioevent_t *pevent = (mstudioevent_t *)((byte *)m_pStudioHeader + pseqdesc->eventindex);

	if( e->latched.sequencetime == e->curstate.animtime )
	{
		if( !FBitSet( pseqdesc->flags, STUDIO_LOOPING ))
			start = -0.01f;
	}

	for( int i = 0; i < pseqdesc->numevents; i++ )
	{
		// ignore all non-client-side events
		if( pevent[i].event < EVENT_CLIENT )
			continue;

		if( (float)pevent[i].frame > start && pevent[i].frame <= end )
			gEngfuncs.pfnStudioEvent( &pevent[i], e );
	}
}

/*
===============
R_StudioGetForceFaceFlags

===============
*/
static int R_StudioGetForceFaceFlags( void )
{
	return g_nForceFaceFlags;
}

/*
===============
R_StudioSetForceFaceFlags

===============
*/
static void R_StudioSetForceFaceFlags( int flags )
{
	g_nForceFaceFlags = flags;
}

/*
===============
pfnStudioSetHeader

===============
*/
static void R_StudioSetHeader( studiohdr_t *pheader )
{
	m_pStudioHeader = pheader;
	m_fDoRemap = false;
}

studiohdr_t *R_StudioGetHeader( void )
{
	return m_pStudioHeader;
}

/*
===============
R_StudioSetRenderModel

===============
*/
static void R_StudioSetRenderModel( model_t *model )
{
	RI.currentmodel = model;
}

/*
===============
R_StudioSetupRenderer

===============
*/
static void R_StudioSetupRenderer( int rendermode )
{
	studiohdr_t	*phdr = m_pStudioHeader;

	if( rendermode > kRenderTransAdd ) rendermode = 0;
	g_studio.rendermode = bound( 0, rendermode, kRenderTransAdd );

	if( g_studio.rendermode == kRenderTransAdd || g_studio.rendermode == kRenderGlow )
		R_AllowFog( false );

	pglTexEnvf( GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE );
	pglDisable( GL_ALPHA_TEST );
	pglShadeModel( GL_SMOOTH );

	// a point to setup local to world transform for boneweighted models
	if( phdr && FBitSet( phdr->flags, STUDIO_HAS_BONEINFO ))
	{
		// NOTE: extended boneinfo goes immediately after bones
		mstudioboneinfo_t *boneinfo = (mstudioboneinfo_t *)((byte *)phdr + phdr->boneindex + phdr->numbones * sizeof( mstudiobone_t ));

		for( int i = 0; i < phdr->numbones; i++ )
			Matrix3x4_ConcatTransforms( g_studio.worldtransform[i], g_studio.bonestransform[i], boneinfo[i].poseToBone );
	}
}

/*
===============
R_StudioRestoreRenderer

===============
*/
static void R_StudioRestoreRenderer( void )
{
	if( g_studio.rendermode != kRenderNormal )
		pglDisable( GL_BLEND );

	if( g_studio.rendermode == kRenderTransAdd || g_studio.rendermode == kRenderGlow )
		R_AllowFog( true );

	pglTexEnvf( GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_REPLACE );
	pglShadeModel( GL_FLAT );
	m_fDoRemap = false;
}

/*
===============
R_StudioSetChromeOrigin

===============
*/
static void R_StudioSetChromeOrigin( void )
{
	VectorCopy( RI.rvp.vieworigin, g_studio.chrome_origin );
}

/*
===============
R_StudioDrawPointsShadow

===============
*/
static void R_StudioDrawPointsShadow( void )
{
	vec3_t		point;

	if( FBitSet( RI.currententity->curstate.effects, EF_NOSHADOW ))
		return;

	if( glState.stencilEnabled )
		pglEnable( GL_STENCIL_TEST );

	float vec_x = -g_studio.lightvec[0] * 8.0f;
	float vec_y = -g_studio.lightvec[1] * 8.0f;

	for( int k = 0; k < m_pSubModel->nummesh; k++ )
	{
		mstudiomesh_t *pmesh = (mstudiomesh_t *)((byte *)m_pStudioHeader + m_pSubModel->meshindex) + k;
		short *ptricmds = (short *)((byte *)m_pStudioHeader + pmesh->triindex);

		r_stats.c_studio_polys += pmesh->numtris;

		int i;
		while(( i = *( ptricmds++ )))
		{
			if( i < 0 )
			{
				pglBegin( GL_TRIANGLE_FAN );
				i = -i;
			}
			else
			{
				pglBegin( GL_TRIANGLE_STRIP );
			}


			for( ; i > 0; i--, ptricmds += 4 )
			{
				float *av = g_studio.verts[ptricmds[0]];
				point[0] = av[0] - (vec_x * ( av[2] - g_studio.lightspot[2] ));
				point[1] = av[1] - (vec_y * ( av[2] - g_studio.lightspot[2] ));
				point[2] = g_studio.lightspot[2] + 1.0f;

				pglVertex3fv( point );
			}

			pglEnd();
		}
	}

	if( glState.stencilEnabled )
		pglDisable( GL_STENCIL_TEST );
}

/*
===============
GL_StudioSetRenderMode

set rendermode for studiomodel
===============
*/
static void GL_StudioSetRenderMode( int rendermode )
{
	switch( rendermode )
	{
	case kRenderNormal:
		break;
	case kRenderTransColor:
		pglBlendFunc( GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA );
		pglTexEnvi( GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE );
		pglEnable( GL_BLEND );
		break;
	case kRenderTransAdd:
		pglTexEnvf( GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE );
		pglColor4f( tr.blend, tr.blend, tr.blend, 1.0f );
		pglBlendFunc( GL_ONE, GL_ONE );
		pglDepthMask( GL_FALSE );
		pglEnable( GL_BLEND );
		break;
	default:
		pglTexEnvf( GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE );
		pglBlendFunc( GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA );
		pglColor4f( 1.0f, 1.0f, 1.0f, tr.blend );
		pglDepthMask( GL_TRUE );
		pglEnable( GL_BLEND );
		break;
	}
}

/*
===============
GL_StudioDrawShadow

g-cont: don't modify this code it's 100% matched with
original GoldSrc code and used in some mods to enable
studio shadows with some asm tricks
===============
*/
static void GL_StudioDrawShadow( void )
{
	pglDepthMask( GL_TRUE );

	if( r_shadows.value && g_studio.rendermode != kRenderTransAdd && !FBitSet( RI.currentmodel->flags, STUDIO_AMBIENT_LIGHT ))
	{
		float	color = 1.0f - (tr.blend * 0.5f);

		pglDisable( GL_TEXTURE_2D );
		pglBlendFunc( GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA );
		pglEnable( GL_BLEND );
		pglColor4f( 0.0f, 0.0f, 0.0f, 1.0f - color );

		pglDepthFunc( GL_LESS );
		R_StudioDrawPointsShadow();
		pglDepthFunc( GL_LEQUAL );

		pglEnable( GL_TEXTURE_2D );
		pglDisable( GL_BLEND );
		pglColor4f( 1.0f, 1.0f, 1.0f, 1.0f );
		pglShadeModel( GL_SMOOTH );
	}
}

/*
====================
StudioRenderFinal

====================
*/
static void R_StudioRenderFinal( void )
{
	int rendermode = R_StudioGetForceFaceFlags() ? kRenderTransAdd : RI.currententity->curstate.rendermode;
	R_StudioSetupRenderer( rendermode );

	if( r_drawentities->value == 2 )
	{
		R_StudioDrawBones();
	}
	else if( r_drawentities->value == 3 )
	{
		R_StudioDrawHulls();
	}
	else
	{
#ifdef XASH_OPENXR
		qboolean is_viewmodel = (RI.currententity == tr.viewent);
		qboolean is_reloading = false;
		if( is_viewmodel && XR_IsActive() && m_pStudioHeader->numseq > 0 )
		{
			int seq_idx = bound( 0, RI.currententity->curstate.sequence, m_pStudioHeader->numseq - 1 );
			mstudioseqdesc_t *pseqdesc = (mstudioseqdesc_t *)((byte *)m_pStudioHeader + m_pStudioHeader->seqindex) + seq_idx;
			if( pseqdesc && Q_stristr( pseqdesc->label, "reload" ) )
				is_reloading = true;
		}
#endif

		for( int i = 0; i < m_pStudioHeader->numbodyparts; i++ )
		{
			R_StudioSetupModel( i, (void**)&m_pBodyPart, (void**)&m_pSubModel );

#ifdef XASH_OPENXR
			// In VR, 1998 flat viewmodels hide spare reload props (like the spare Glock clip,
			// 357 speedloader, or shotgun reload shell) by animating them -25 units below the 2D screen edge.
			// In 6DoF VR, this leaves spare magazines floating in mid-air below the player's hand when not reloading!
			// Suppress spare reload submodels unless the weapon is actively performing a reload sequence.
			if( is_viewmodel && XR_IsActive() && !is_reloading && m_pSubModel )
			{
				if( !Q_stricmp( m_pSubModel->name, "clip_reference" ) ||
				    !Q_stricmp( m_pSubModel->name, "python_speedload" ) ||
				    (!Q_stricmp( m_pSubModel->name, "shell" ) && RI.currentmodel && Q_stristr( RI.currentmodel->name, "shotgun" )) )
				{
					continue; // Do not render offscreen reload prop in VR when not reloading
				}
			}
#endif

			GL_StudioSetRenderMode( rendermode );
			R_StudioDrawPoints();
			GL_StudioDrawShadow();
		}
	}

	if( r_drawentities->value == 4 )
	{
		TriRenderMode( kRenderTransAdd );
		R_StudioDrawHulls( );
		TriRenderMode( kRenderNormal );
	}

	if( r_drawentities->value == 5 )
	{
		R_StudioDrawAbsBBox( );
	}

	if( r_drawentities->value == 6 )
	{
		R_StudioDrawAttachments();
	}

	if( r_drawentities->value == 7 )
	{
		vec3_t	origin;

		pglDisable( GL_TEXTURE_2D );
		pglDisable( GL_DEPTH_TEST );

		Matrix3x4_OriginFromMatrix( g_studio.rotationmatrix, origin );

		pglBegin( GL_LINES );
		pglColor3f( 1, 0.5, 0 );
		pglVertex3fv( origin );
		pglVertex3fv( g_studio.lightspot );
		pglEnd();

		pglBegin( GL_LINES );
		pglColor3f( 0, 0.5, 1 );
		VectorMA( g_studio.lightspot, -64.0f, g_studio.lightvec, origin );
		pglVertex3fv( g_studio.lightspot );
		pglVertex3fv( origin );
		pglEnd();

		pglPointSize( 5.0f );
		pglColor3f( 1, 0, 0 );
		pglBegin( GL_POINTS );
		pglVertex3fv( g_studio.lightspot );
		pglEnd();
		pglPointSize( 1.0f );

		pglEnable( GL_DEPTH_TEST );
		pglEnable( GL_TEXTURE_2D );
	}

	R_StudioRestoreRenderer();
}

/*
====================
StudioRenderModel

====================
*/
static void R_StudioRenderModel( void )
{
	R_StudioSetChromeOrigin();
	R_StudioSetForceFaceFlags( 0 );

	if( RI.currententity->curstate.renderfx == kRenderFxGlowShell )
	{
		RI.currententity->curstate.renderfx = kRenderFxNone;

		R_StudioRenderFinal( );

		R_StudioSetForceFaceFlags( STUDIO_NF_CHROME );
		TriSpriteTexture( gEngfuncs.GetDefaultSprite( REF_CHROME_SPRITE ), 0 );
		RI.currententity->curstate.renderfx = kRenderFxGlowShell;

		R_StudioRenderFinal( );
	}
	else
	{
		R_StudioRenderFinal( );
	}
}

/*
====================
StudioEstimateGait

====================
*/
static void R_StudioEstimateGait( entity_state_t *pplayer )
{
	vec3_t	est_velocity;
	float dt = bound( 0.0f, g_studio.frametime, 1.0f );

	if( dt == 0.0f || m_pPlayerInfo->renderframe == tr.realframecount )
	{
		m_flGaitMovement = 0;
		return;
	}

	VectorSubtract( RI.currententity->origin, m_pPlayerInfo->prevgaitorigin, est_velocity );
	VectorCopy( RI.currententity->origin, m_pPlayerInfo->prevgaitorigin );
	m_flGaitMovement = VectorLength( est_velocity );

	if( dt <= 0.0f || m_flGaitMovement / dt < 5.0f )
	{
		m_flGaitMovement = 0.0f;
		est_velocity[0] = 0.0f;
		est_velocity[1] = 0.0f;
	}

	if( est_velocity[1] == 0.0f && est_velocity[0] == 0.0f )
	{
		float	flYawDiff = RI.currententity->angles[YAW] - m_pPlayerInfo->gaityaw;

		flYawDiff = flYawDiff - (int)(flYawDiff / 360) * 360;
		if( flYawDiff > 180.0f ) flYawDiff -= 360.0f;
		if( flYawDiff < -180.0f ) flYawDiff += 360.0f;

		if( dt < 0.25f )
			flYawDiff *= dt * 4.0f;
		else flYawDiff *= dt;

		m_pPlayerInfo->gaityaw += flYawDiff;
		m_pPlayerInfo->gaityaw = m_pPlayerInfo->gaityaw - (int)(m_pPlayerInfo->gaityaw / 360) * 360;

		m_flGaitMovement = 0.0f;
	}
	else
	{
		m_pPlayerInfo->gaityaw = ( atan2( est_velocity[1], est_velocity[0] ) * 180 / M_PI_F );
		if( m_pPlayerInfo->gaityaw > 180.0f ) m_pPlayerInfo->gaityaw = 180.0f;
		if( m_pPlayerInfo->gaityaw < -180.0f ) m_pPlayerInfo->gaityaw = -180.0f;
	}

}

/*
====================
StudioProcessGait

====================
*/
static void R_StudioProcessGait( entity_state_t *pplayer )
{
	if( RI.currententity->curstate.sequence >= m_pStudioHeader->numseq )
		RI.currententity->curstate.sequence = 0;

	float dt = bound( 0.0f, g_studio.frametime, 1.0f );

	mstudioseqdesc_t *pseqdesc = (mstudioseqdesc_t *)((byte *)m_pStudioHeader + m_pStudioHeader->seqindex) + RI.currententity->curstate.sequence;

	int iBlend;
	R_StudioPlayerBlend( pseqdesc, &iBlend, &RI.currententity->angles[PITCH] );

	RI.currententity->latched.prevangles[PITCH] = RI.currententity->angles[PITCH];
	RI.currententity->curstate.blending[0] = iBlend;
	RI.currententity->latched.prevblending[0] = RI.currententity->curstate.blending[0];
	RI.currententity->latched.prevseqblending[0] = RI.currententity->curstate.blending[0];
	R_StudioEstimateGait( pplayer );

	// calc side to side turning
	float flYaw = RI.currententity->angles[YAW] - m_pPlayerInfo->gaityaw;
	flYaw = flYaw - (int)(flYaw / 360) * 360;
	if( flYaw < -180.0f ) flYaw = flYaw + 360.0f;
	if( flYaw > 180.0f ) flYaw = flYaw - 360.0f;

	if( flYaw > 120.0f )
	{
		m_pPlayerInfo->gaityaw = m_pPlayerInfo->gaityaw - 180.0f;
		m_flGaitMovement = -m_flGaitMovement;
		flYaw = flYaw - 180.0f;
	}
	else if( flYaw < -120.0f )
	{
		m_pPlayerInfo->gaityaw = m_pPlayerInfo->gaityaw + 180.0f;
		m_flGaitMovement = -m_flGaitMovement;
		flYaw = flYaw + 180.0f;
	}

	// adjust torso
	RI.currententity->curstate.controller[0] = ((flYaw / 4.0f) + 30.0f) / (60.0f / 255.0f);
	RI.currententity->curstate.controller[1] = ((flYaw / 4.0f) + 30.0f) / (60.0f / 255.0f);
	RI.currententity->curstate.controller[2] = ((flYaw / 4.0f) + 30.0f) / (60.0f / 255.0f);
	RI.currententity->curstate.controller[3] = ((flYaw / 4.0f) + 30.0f) / (60.0f / 255.0f);
	RI.currententity->latched.prevcontroller[0] = RI.currententity->curstate.controller[0];
	RI.currententity->latched.prevcontroller[1] = RI.currententity->curstate.controller[1];
	RI.currententity->latched.prevcontroller[2] = RI.currententity->curstate.controller[2];
	RI.currententity->latched.prevcontroller[3] = RI.currententity->curstate.controller[3];

	RI.currententity->angles[YAW] = m_pPlayerInfo->gaityaw;
	if( RI.currententity->angles[YAW] < -0 ) RI.currententity->angles[YAW] += 360.0f;
	RI.currententity->latched.prevangles[YAW] = RI.currententity->angles[YAW];

	if( pplayer->gaitsequence >= m_pStudioHeader->numseq )
		pplayer->gaitsequence = 0;

	pseqdesc = (mstudioseqdesc_t *)((byte *)m_pStudioHeader + m_pStudioHeader->seqindex) + pplayer->gaitsequence;

	// calc gait frame
	if( pseqdesc->linearmovement[0] > 0 )
		m_pPlayerInfo->gaitframe += (m_flGaitMovement / pseqdesc->linearmovement[0]) * pseqdesc->numframes;
	else m_pPlayerInfo->gaitframe += pseqdesc->fps * dt;

	// do modulo
	m_pPlayerInfo->gaitframe = m_pPlayerInfo->gaitframe - (int)(m_pPlayerInfo->gaitframe / pseqdesc->numframes) * pseqdesc->numframes;
	if( m_pPlayerInfo->gaitframe < 0 ) m_pPlayerInfo->gaitframe += pseqdesc->numframes;
}

/*
===============
R_StudioDrawPlayer

===============
*/
static int R_StudioDrawPlayer( int flags, entity_state_t *pplayer )
{
	alight_t	lighting;
	vec3_t	dir;

	int m_nPlayerIndex = pplayer->number - 1;

	if( m_nPlayerIndex < 0 || m_nPlayerIndex >= gp_cl->maxclients )
		return 0;

	RI.currentmodel = R_StudioSetupPlayerModel( m_nPlayerIndex );
	if( RI.currentmodel == NULL )
		return 0;

	R_StudioSetHeader((studiohdr_t *)gEngfuncs.Mod_Extradata( mod_studio, RI.currentmodel ));

	if( pplayer->gaitsequence )
	{
		m_pPlayerInfo = pfnPlayerInfo( m_nPlayerIndex );
		vec3_t orig_angles = Vec3( RI.currententity->angles );

		R_StudioProcessGait( pplayer );

		m_pPlayerInfo->gaitsequence = pplayer->gaitsequence;
		m_pPlayerInfo = NULL;

		R_StudioSetUpTransform( RI.currententity );
		VectorCopy( orig_angles, RI.currententity->angles );
	}
	else
	{
		RI.currententity->curstate.controller[0] = 127;
		RI.currententity->curstate.controller[1] = 127;
		RI.currententity->curstate.controller[2] = 127;
		RI.currententity->curstate.controller[3] = 127;
		RI.currententity->latched.prevcontroller[0] = RI.currententity->curstate.controller[0];
		RI.currententity->latched.prevcontroller[1] = RI.currententity->curstate.controller[1];
		RI.currententity->latched.prevcontroller[2] = RI.currententity->curstate.controller[2];
		RI.currententity->latched.prevcontroller[3] = RI.currententity->curstate.controller[3];

		m_pPlayerInfo = pfnPlayerInfo( m_nPlayerIndex );
		m_pPlayerInfo->gaitsequence = 0;

		R_StudioSetUpTransform( RI.currententity );
	}

	if( flags & STUDIO_RENDER )
	{
		// see if the bounding box lets us trivially reject, also sets
		if( !R_StudioCheckBBox( ))
			return 0;

		r_stats.c_studio_models_drawn++;
		g_studio.framecount++; // render data cache cookie

		if( m_pStudioHeader->numbodyparts == 0 )
			return 1;
	}

	m_pPlayerInfo = pfnPlayerInfo( m_nPlayerIndex );
	R_StudioSetupBones( RI.currententity );
	R_StudioSaveBones( );

	m_pPlayerInfo->renderframe = tr.realframecount;
	m_pPlayerInfo = NULL;

	if( (flags & STUDIO_EVENTS) || (RI.currententity == tr.viewent && XR_IsActive()) )
	{
		R_StudioCalcAttachments( );
		R_StudioClientEvents( );

		// copy attachments into global entity array
		if( RI.currententity->index > 0 )
		{
			cl_entity_t *ent = CL_GetEntityByIndex( RI.currententity->index );
			memcpy( ent->attachment, RI.currententity->attachment, sizeof( vec3_t ) * 4 );
		}
	}

	if( flags & STUDIO_RENDER )
	{
		// change body if it's a menu entity
		if( cl_himodels->value && ( RI.currentmodel != RI.currententity->model || !FBitSet( RI.rvp.flags, RF_DRAW_WORLD )))
		{
			// show highest resolution multiplayer model
			RI.currententity->curstate.body = 255;
		}

		if( !( !gpGlobals->developer && gp_cl->maxclients == 1 ) && ( RI.currentmodel == RI.currententity->model ))
			RI.currententity->curstate.body = 1; // force helmet

		lighting.plightvec = dir;
		R_EntityDynamicLight( RI.currententity, &lighting, FBitSet( RI.rvp.flags, RF_DRAW_WORLD ), g_studio.time, g_studio.lightspot, g_studio.lightvec );

		R_StudioEntityLight( &lighting );

		// model and frame independant
		R_StudioSetupLighting( &lighting );

		m_pPlayerInfo = pfnPlayerInfo( m_nPlayerIndex );

		// get remap colors
		g_nTopColor = m_pPlayerInfo->topcolor;
		g_nBottomColor = m_pPlayerInfo->bottomcolor;

		if( g_nTopColor < 0 ) g_nTopColor = 0;
		if( g_nTopColor > 360 ) g_nTopColor = 360;
		if( g_nBottomColor < 0 ) g_nBottomColor = 0;
		if( g_nBottomColor > 360 ) g_nBottomColor = 360;

		R_StudioSetRemapColors( g_nTopColor, g_nBottomColor );

		R_StudioRenderModel( );
		m_pPlayerInfo = NULL;

		if( pplayer->weaponmodel )
		{
			cl_entity_t	saveent = *RI.currententity;
			model_t		*pweaponmodel = CL_ModelHandle( pplayer->weaponmodel );

			m_pStudioHeader = (studiohdr_t *)gEngfuncs.Mod_Extradata( mod_studio, pweaponmodel );

			R_StudioMergeBones( RI.currententity, pweaponmodel );
			R_StudioSetupLighting( &lighting );
			R_StudioRenderModel( );
			R_StudioCalcAttachments( );

			*RI.currententity = saveent;
		}
	}

	return 1;
}

/*
===============
R_StudioDrawModel

===============
*/
static int R_StudioDrawModel( int flags )
{
	alight_t	lighting;
	vec3_t	dir;

	if( RI.currententity->curstate.renderfx == kRenderFxDeadPlayer )
	{
		if( RI.currententity->curstate.renderamt <= 0 ||
			RI.currententity->curstate.renderamt > gp_cl->maxclients )
			return 0;

		// get copy of player
		entity_state_t deadplayer = *R_StudioGetPlayerState( RI.currententity->curstate.renderamt - 1 );

		// clear weapon, movement state
		deadplayer.number = RI.currententity->curstate.renderamt;
		deadplayer.weaponmodel = 0;
		deadplayer.gaitsequence = 0;

		deadplayer.movetype = MOVETYPE_NONE;
		VectorCopy( RI.currententity->curstate.angles, deadplayer.angles );
		VectorCopy( RI.currententity->curstate.origin, deadplayer.origin );

		g_studio.interpolate = false;
		int result = R_StudioDrawPlayer( flags, &deadplayer ); // draw as though it were a player
		g_studio.interpolate = true;

		return result;
	}

	R_StudioSetHeader((studiohdr_t *)gEngfuncs.Mod_Extradata( mod_studio, RI.currentmodel ));

	R_StudioSetUpTransform( RI.currententity );

	if( flags & STUDIO_RENDER )
	{
		// see if the bounding box lets us trivially reject, also sets
		if( !R_StudioCheckBBox( ))
			return 0;

		r_stats.c_studio_models_drawn++;
		g_studio.framecount++; // render data cache cookie

		if( m_pStudioHeader->numbodyparts == 0 )
			return 1;
	}

	if( RI.currententity->curstate.movetype == MOVETYPE_FOLLOW )
		R_StudioMergeBones( RI.currententity, RI.currentmodel );
	else R_StudioSetupBones( RI.currententity );

	R_VR_DebugGripBone( RI.currententity, RI.currentmodel );

	R_StudioSaveBones();

	if( flags & STUDIO_EVENTS )
	{
		R_StudioCalcAttachments( );
		R_StudioClientEvents( );

		// copy attachments into global entity array
		if( RI.currententity->index > 0 )
		{
			cl_entity_t *ent = CL_GetEntityByIndex( RI.currententity->index );
			memcpy( ent->attachment, RI.currententity->attachment, sizeof( vec3_t ) * 4 );
		}
	}

	if( flags & STUDIO_RENDER )
	{
		lighting.plightvec = dir;
		R_EntityDynamicLight( RI.currententity, &lighting, FBitSet( RI.rvp.flags, RF_DRAW_WORLD ), g_studio.time, g_studio.lightspot, g_studio.lightvec );

		R_StudioEntityLight( &lighting );

		// model and frame independant
		R_StudioSetupLighting( &lighting );

		// get remap colors
		g_nTopColor = RI.currententity->curstate.colormap & 0xFF;
		g_nBottomColor = (RI.currententity->curstate.colormap & 0xFF00) >> 8;

		R_StudioSetRemapColors( g_nTopColor, g_nBottomColor );

		R_StudioRenderModel();
	}

	return 1;
}

/*
=================
R_StudioDrawModelInternal
=================
*/
static void R_StudioDrawModelInternal( cl_entity_t *e, int flags )
{
#ifdef XASH_OPENXR
	// In VR, the viewmodel and offhand are 6DoF hand-tracked entities that must use our decoupled studio renderer
	if( ((e == tr.viewent || e == &s_offhandEnt || e == &s_primaryHandEnt) && XR_IsActive()) || !FBitSet( RI.rvp.flags, RF_DRAW_WORLD ) || unlikely( r_studio_builtin_renderer.value ))
#else
	if( !FBitSet( RI.rvp.flags, RF_DRAW_WORLD ) || unlikely( r_studio_builtin_renderer.value ))
#endif
	{
		if( e->player )
			R_StudioDrawPlayer( flags, &e->curstate );
		else R_StudioDrawModel( flags );
	}
	else
	{
		// select the properly method
		if( e->player )
			pStudioDraw->StudioDrawPlayer( flags, R_StudioGetPlayerState( e->index - 1 ));
		else pStudioDraw->StudioDrawModel( flags );
	}
}

static cl_entity_t *R_FindParentEntity( cl_entity_t *e, cl_entity_t **entities, uint num_entities )
{
	for( uint i = 0; i < num_entities; i++ )
	{
		if( entities[i]->index == e->curstate.aiment )
			return entities[i];
	}

	return NULL;
}

/*
=================
R_DrawStudioModel
=================
*/
void R_DrawStudioModel( cl_entity_t *e )
{
	if( FBitSet( RI.rvp.flags, RF_DRAW_CUBEMAP ))
		return;

	R_StudioSetupTimings();

	if( e->player )
	{
		R_StudioDrawModelInternal( e, STUDIO_RENDER|STUDIO_EVENTS );
	}
	else if( e->curstate.movetype == MOVETYPE_FOLLOW )
	{
		cl_entity_t *parent = CL_GetEntityByIndex( e->curstate.aiment );

		if( !parent || !parent->model || parent->model->type != mod_studio )
			return;

		parent = R_FindParentEntity( e, tr.draw_list->solid_entities, tr.draw_list->num_solid_entities );

		if( !parent )
			parent = R_FindParentEntity( e, tr.draw_list->trans_entities, tr.draw_list->num_trans_entities );

		if( parent )
		{
			RI.currententity = parent;
			R_StudioDrawModelInternal( RI.currententity, 0 );
			VectorCopy( RI.currententity->curstate.origin, e->curstate.origin );
			VectorCopy( RI.currententity->origin, e->origin );
			RI.currententity = e;

			R_StudioDrawModelInternal( e, STUDIO_RENDER|STUDIO_EVENTS );
		}
	}
	else
	{
		R_StudioDrawModelInternal( e, STUDIO_RENDER|STUDIO_EVENTS );
	}
}

/*
=================
R_RunViewmodelEvents
=================
*/
void R_RunViewmodelEvents( void )
{
	if( r_drawviewmodel->value == 0 )
		return;

	if( ENGINE_GET_PARM( PARM_THIRDPERSON ))
		return;

	// ignore in thirdperson, camera view or client is died
	if( FBitSet( RI.rvp.flags, RF_DRAW_CUBEMAP ) || ENGINE_GET_PARM( PARM_LOCAL_HEALTH ) <= 0 || !CL_IsViewEntityLocalPlayer())
		return;

	RI.currententity = tr.viewent;

	if( !RI.currententity->model || RI.currententity->model->type != mod_studio )
		return;

	R_StudioSetupTimings();

	vec3_t simorg = Vec3( gp_cl->simorg );
	for( int i = 0; i < 4; i++ )
		VectorCopy( simorg, RI.currententity->attachment[i] );
	RI.currentmodel = RI.currententity->model;

	R_StudioDrawModelInternal( RI.currententity, STUDIO_EVENTS );
}

#ifdef XASH_OPENXR
/*
====================
R_VR_DebugHandPose

Regression telemetry: prints machine-parseable world-space landmark bone
positions for a standalone hand entity. Landmarks are the wrist, palm,
middle fingertip and thumb tip, keyed by the Valve bone naming convention.
Gated behind vr_debug_hand_pose and throttled to about once per second per
entity so the log stays readable.
====================
*/
static void R_VR_DebugHandPose( cl_entity_t *ent, model_t *model )
{
	static cvar_t *vr_debug_hand_pose = NULL;
	if( !vr_debug_hand_pose ) vr_debug_hand_pose = gEngfuncs.pfnGetCvarPointer( "vr_debug_hand_pose" );
	if( !vr_debug_hand_pose || vr_debug_hand_pose->value <= 0.0f )
		return;

	if( !model || model->type != mod_studio )
		return;

	studiohdr_t *header = (studiohdr_t *)model->cache.data;
	if( !header )
		return;

	mstudiobone_t *pbones = (mstudiobone_t *)((byte *)header + header->boneindex);

	// The left chain is drawn by the left-body entity; everything else uses
	// the right chain. Handles vr_lefthanded automatically since the body
	// value already encodes which chain the entity is drawing.
	const char *prefix = ( ent->curstate.body >= 3 ) ? "L" : "R";

	char name_wrist[64], name_palm[64], name_tip[64], name_thumb[64], name_thumbbase[64];
	Q_snprintf( name_wrist, sizeof( name_wrist ), "Bip01 %s Hand", prefix );
	Q_snprintf( name_palm,  sizeof( name_palm ),  "Bip01 %s Palm", prefix );
	Q_snprintf( name_tip,   sizeof( name_tip ),   "Bip01 %s Finger22", prefix );
	Q_snprintf( name_thumb, sizeof( name_thumb ), "Bip01 %s Finger01", prefix );
	Q_snprintf( name_thumbbase, sizeof( name_thumbbase ), "Bip01 %s Finger0", prefix );

	int i_wrist = -1, i_palm = -1, i_tip = -1, i_thumb = -1, i_thumbbase = -1;
	for( int i = 0; i < header->numbones; i++ )
	{
		if( i_wrist < 0 && !Q_strcmp( pbones[i].name, name_wrist )) i_wrist = i;
		if( i_palm  < 0 && !Q_strcmp( pbones[i].name, name_palm  )) i_palm  = i;
		if( i_tip   < 0 && !Q_strcmp( pbones[i].name, name_tip   )) i_tip   = i;
		if( i_thumb < 0 && !Q_strcmp( pbones[i].name, name_thumb )) i_thumb = i;
		if( i_thumbbase < 0 && !Q_strcmp( pbones[i].name, name_thumbbase )) i_thumbbase = i;
	}

	if( i_palm < 0 || i_tip < 0 || i_thumb < 0 )
		return;

	// Throttle to one line per second per entity to keep the log compact.
	static float s_last[2] = { -10.0f, -10.0f };
	int slot = ( ent == &s_primaryHandEnt ) ? 0 : 1;
	if( g_studio.time - s_last[slot] < 1.0f )
		return;
	s_last[slot] = g_studio.time;

	const char *entname = ( ent == &s_primaryHandEnt ) ? "primary" : "offhand";
	matrix3x4 *bt = g_studio.bonestransform;

	// Local frame of the drawn hand, taken from the same rotation matrix used to
	// build the bones. This makes the orientation assertions pose-invariant: the
	// hand may face any world direction, but fingers must align with its forward
	// axis and the thumb with its up axis.
	vec3_t fwd, up;
	fwd[0] = g_studio.rotationmatrix[0][0];
	fwd[1] = g_studio.rotationmatrix[1][0];
	fwd[2] = g_studio.rotationmatrix[2][0];
	up[0] = g_studio.rotationmatrix[0][2];
	up[1] = g_studio.rotationmatrix[1][2];
	up[2] = g_studio.rotationmatrix[2][2];

	gEngfuncs.Con_Printf(
		"^5[HAND_POSE] ent=%s body=%d chain=%s palm=(%.3f %.3f %.3f) fingertip=(%.3f %.3f %.3f) thumb=(%.3f %.3f %.3f) thumbbase=(%.3f %.3f %.3f) wrist=(%.3f %.3f %.3f) fwd=(%.3f %.3f %.3f) up=(%.3f %.3f %.3f)\n",
		entname, (int)ent->curstate.body, prefix,
		bt[i_palm][0][3],  bt[i_palm][1][3],  bt[i_palm][2][3],
		bt[i_tip][0][3],   bt[i_tip][1][3],   bt[i_tip][2][3],
		bt[i_thumb][0][3], bt[i_thumb][1][3], bt[i_thumb][2][3],
		(i_thumbbase >= 0) ? bt[i_thumbbase][0][3] : 0.0f,
		(i_thumbbase >= 0) ? bt[i_thumbbase][1][3] : 0.0f,
		(i_thumbbase >= 0) ? bt[i_thumbbase][2][3] : 0.0f,
		(i_wrist >= 0) ? bt[i_wrist][0][3] : 0.0f,
		(i_wrist >= 0) ? bt[i_wrist][1][3] : 0.0f,
		(i_wrist >= 0) ? bt[i_wrist][2][3] : 0.0f,
		fwd[0], fwd[1], fwd[2], up[0], up[1], up[2] );
}

/*
====================
R_VR_DebugGripBone

Calibration telemetry: prints the world-space and weapon-local position of
the real grip anchor inside the active viewmodel. The anchor is the animated
"grip" bone when present (crossbow) and the original "Bip01 R Hand" bone
otherwise. The weapon-local position is what seeds grip_offset:

    grip_offset = palm - anchor - global_offset

where palm is the hand model origin (0,0,0). Gated behind vr_grip_probe and
throttled to one line per second per model.
====================
*/
static void R_VR_DebugGripBone( cl_entity_t *ent, model_t *model )
{
#ifdef XASH_OPENXR
	static cvar_t *vr_grip_probe = NULL;
	if( !vr_grip_probe ) vr_grip_probe = gEngfuncs.pfnGetCvarPointer( "vr_grip_probe" );
	if( !vr_grip_probe || vr_grip_probe->value <= 0.0f )
		return;

	if( ent != tr.viewent || !ent->model || !model || model->type != mod_studio )
		return;

	studiohdr_t *header = (studiohdr_t *)model->cache.data;
	if( !header )
		return;

	mstudiobone_t *pbones = (mstudiobone_t *)((byte *)header + header->boneindex);

	int grip = -1;
	static const char *fallback_bones[] = { "Bip01 R Hand", "Xbow biped R Hand", "Bone09", "Bip01 L Hand", "grip" };
	for( size_t b = 0; b < sizeof(fallback_bones) / sizeof(fallback_bones[0]) && grip < 0; b++ )
	{
		for( int i = 0; i < header->numbones; i++ )
		{
			if( !Q_strcmp( pbones[i].name, fallback_bones[b] ))
			{
				grip = i;
				break;
			}
		}
	}
	if( grip < 0 )
		return;

	// Log once per (model, sequence) so every animation state is captured
	// without flooding the log.
	static model_t *s_lastModel = NULL;
	static int s_lastSeq = -1;
	if( model == s_lastModel && (int)ent->curstate.sequence == s_lastSeq )
		return;
	s_lastModel = model;
	s_lastSeq = (int)ent->curstate.sequence;

	matrix3x4 *bt = g_studio.bonestransform;
	vec3_t world = { bt[grip][0][3], bt[grip][1][3], bt[grip][2][3] };

	// Convert the world anchor into weapon-local coordinates using the exact
	// entity matrix that was used to build the bones. Inverting by
	// reconstructing Euler angles is fragile because the renderer's pitch
	// convention differs from AngleVectors.
	vec3_t d = {
		world[0] - g_studio.rotationmatrix[0][3],
		world[1] - g_studio.rotationmatrix[1][3],
		world[2] - g_studio.rotationmatrix[2][3]
	};
	vec3_t local;
	local[0] = g_studio.rotationmatrix[0][0] * d[0] + g_studio.rotationmatrix[1][0] * d[1] + g_studio.rotationmatrix[2][0] * d[2];
	local[1] = g_studio.rotationmatrix[0][1] * d[0] + g_studio.rotationmatrix[1][1] * d[1] + g_studio.rotationmatrix[2][1] * d[2];
	local[2] = g_studio.rotationmatrix[0][2] * d[0] + g_studio.rotationmatrix[1][2] * d[1] + g_studio.rotationmatrix[2][2] * d[2];

	// Bone basis in weapon-local space (columns are the bone's local axes).
	vec3_t bx, by, bz;
	for( int r = 0; r < 3; r++ )
	{
		bx[r] = g_studio.rotationmatrix[0][r] * bt[grip][0][0] + g_studio.rotationmatrix[1][r] * bt[grip][1][0] + g_studio.rotationmatrix[2][r] * bt[grip][2][0];
		by[r] = g_studio.rotationmatrix[0][r] * bt[grip][0][1] + g_studio.rotationmatrix[1][r] * bt[grip][1][1] + g_studio.rotationmatrix[2][r] * bt[grip][2][1];
		bz[r] = g_studio.rotationmatrix[0][r] * bt[grip][0][2] + g_studio.rotationmatrix[1][r] * bt[grip][1][2] + g_studio.rotationmatrix[2][r] * bt[grip][2][2];
	}

	// Sequence label helps post-processing pick the rest/idle pose instead of
	// a shoot or throw animation.
	const char *seq_label = "";
	if( ent->curstate.sequence >= 0 && ent->curstate.sequence < header->numseq )
	{
		mstudioseqdesc_t *pseq = (mstudioseqdesc_t *)((byte *)header + header->seqindex) + ent->curstate.sequence;
		seq_label = pseq->label;
	}

	// Seat error: distance from the weapon grip anchor to the world hand origin
	// that XR_GetWeaponPose used. With a correct grip_offset this is near zero
	// (a sub-unit residual comes from the wrist/palm offset).
	float seat_err = -1.0f;
	vec3_t horg, hang;
	if( XR_GetPrimaryHandTransform( horg, hang ))
	{
		float scale = ( vr_worldscale && vr_worldscale->value > 0.0f ) ? vr_worldscale->value : 40.0f;
		float turn_yaw = XR_GetPlayerTurnYaw();
		float ya = DEG2RAD( turn_yaw );
		vec3_t hand_world = {
			RI.rvp.vieworigin[0] + ( horg[0] * cosf( ya ) - horg[1] * sinf( ya )) * scale,
			RI.rvp.vieworigin[1] + ( horg[0] * sinf( ya ) + horg[1] * cosf( ya )) * scale,
			RI.rvp.vieworigin[2] + horg[2] * scale
		};
		seat_err = VectorDistance( world, hand_world );
	}

	gEngfuncs.Con_Printf( "^5[VR_GRIP_BONE] model=%s bone=%s seq=%d label=%s frame=%.2f world=(%.3f %.3f %.3f) model=(%.3f %.3f %.3f) seat_err=%.3f bx=(%.3f %.3f %.3f) by=(%.3f %.3f %.3f) bz=(%.3f %.3f %.3f)\n",
		model->name, pbones[grip].name,
		(int)ent->curstate.sequence, seq_label, ent->curstate.frame,
		world[0], world[1], world[2],
		local[0], local[1], local[2],
		seat_err,
		bx[0], bx[1], bx[2], by[0], by[1], by[2], bz[0], bz[1], bz[2] );

	// Extended mode (vr_grip_probe 2): dump every two-hand landmark bone so a
	// reference model (e.g. the MMOD reanimation pack) can provide the main
	// grip and the offhand foregrip positions.
	if( vr_grip_probe->value >= 2.0f )
	{
		static const char *landmarks[] = {
			"grip", "Bip01 R Hand", "Bip01 L Hand",
			"Xbow biped R Hand", "Xbow biped L Hand",
			"LeftArm", "RightArm", "LA4", "RA4"
		};

		for( size_t l = 0; l < sizeof(landmarks) / sizeof(landmarks[0]); l++ )
		{
			int idx = -1;
			for( int i = 0; i < header->numbones; i++ )
			{
				if( !Q_strcmp( pbones[i].name, landmarks[l] ))
				{
					idx = i;
					break;
				}
			}
			if( idx < 0 )
				continue;

			vec3_t bw = { bt[idx][0][3], bt[idx][1][3], bt[idx][2][3] };
			vec3_t bd = {
				bw[0] - g_studio.rotationmatrix[0][3],
				bw[1] - g_studio.rotationmatrix[1][3],
				bw[2] - g_studio.rotationmatrix[2][3]
			};
			vec3_t bl;
			bl[0] = g_studio.rotationmatrix[0][0] * bd[0] + g_studio.rotationmatrix[1][0] * bd[1] + g_studio.rotationmatrix[2][0] * bd[2];
			bl[1] = g_studio.rotationmatrix[0][1] * bd[0] + g_studio.rotationmatrix[1][1] * bd[1] + g_studio.rotationmatrix[2][1] * bd[2];
			bl[2] = g_studio.rotationmatrix[0][2] * bd[0] + g_studio.rotationmatrix[1][2] * bd[1] + g_studio.rotationmatrix[2][2] * bd[2];

			vec3_t mbx, mby, mbz;
			for( int r = 0; r < 3; r++ )
			{
				mbx[r] = g_studio.rotationmatrix[0][r] * bt[idx][0][0] + g_studio.rotationmatrix[1][r] * bt[idx][1][0] + g_studio.rotationmatrix[2][r] * bt[idx][2][0];
				mby[r] = g_studio.rotationmatrix[0][r] * bt[idx][0][1] + g_studio.rotationmatrix[1][r] * bt[idx][1][1] + g_studio.rotationmatrix[2][r] * bt[idx][2][1];
				mbz[r] = g_studio.rotationmatrix[0][r] * bt[idx][0][2] + g_studio.rotationmatrix[1][r] * bt[idx][1][2] + g_studio.rotationmatrix[2][r] * bt[idx][2][2];
			}

			gEngfuncs.Con_Printf( "^5[VR_GRIP_BONES] model=%s bone=%s seq=%d label=%s world=(%.3f %.3f %.3f) model=(%.3f %.3f %.3f) bx=(%.3f %.3f %.3f) by=(%.3f %.3f %.3f) bz=(%.3f %.3f %.3f)\n",
				model->name, pbones[idx].name,
				(int)ent->curstate.sequence, seq_label,
				bw[0], bw[1], bw[2],
				bl[0], bl[1], bl[2],
				mbx[0], mbx[1], mbx[2], mby[0], mby[1], mby[2], mbz[0], mbz[1], mbz[2] );
		}
	}
#else
	(void)ent;
	(void)model;
#endif
}

/*
====================
R_DrawHandEntity

Renders a standalone hand presence entity with the 6DoF controller pose.
====================
*/
static void R_DrawHandEntity( cl_entity_t *ent, model_t *model )
{
	if( !ent || !model || model->type != mod_studio )
		return;

	ent->model = model;
	ent->curstate.sequence = 0;
	ent->curstate.frame = 0;

	// Two-hand model: bodygroup 0 draws the right chain, bodygroup 1 the left.
	// With the bodygroup base arithmetic, body 0 selects the right hand and
	// body 3 selects the left hand. Each entity draws the chain matching the
	// controller that drives it, so no mirroring is needed.
	{
		qboolean lefthanded = ( vr_lefthanded && vr_lefthanded->value > 0.0f );
		qboolean primary = ( ent == &s_primaryHandEnt );
		ent->curstate.body = ( primary != lefthanded ) ? 0 : 3;
	}

	ent->curstate.rendermode = kRenderNormal;

	cl_entity_t *saved_current = RI.currententity;
	model_t *saved_model = RI.currentmodel;

	RI.currententity = ent;
	RI.currentmodel  = ent->model;

	R_StudioSetupTimings();
	R_StudioDrawModelInternal( ent, STUDIO_RENDER );

	// Emit the landmark telemetry after the draw so the bone transforms are
	// the exact ones used to render this hand.
	R_StudioSetupBones( ent );
	R_VR_DebugHandPose( ent, model );

	RI.currententity = saved_current;
	RI.currentmodel  = saved_model;
}

/*
====================
R_DrawOffHand

Renders the independent 6DoF off-hand (secondary controller) model when
the active weapon viewmodel doesn't contain the secondary hand.
====================
*/
static void R_DrawOffHand( void )
{
	static cvar_t *vr_offhand_render = NULL;
	if( !vr_offhand_render ) vr_offhand_render = gEngfuncs.pfnGetCvarPointer( "vr_offhand_render" );
	if( !vr_offhand_render || vr_offhand_render->value <= 0.0f )
		return;

	model_t *handModel = R_LoadVrHandModel( false );
	if( !handModel || handModel->type != mod_studio )
		return;

	vec3_t dummyOrigin, dummyAngles;
	if( !XR_GetHandPresenceTransform( R_VR_SecondaryHandIndex(), dummyOrigin, dummyAngles ) )
		return;

	R_DrawHandEntity( &s_offhandEnt, handModel );
}

/*
====================
R_DrawPrimaryHand

Renders a standalone primary hand when no weapon viewmodel provides one
(empty hands, pre-spawn, weapon hidden or not yet streamed in).
====================
*/
static void R_DrawPrimaryHand( void )
{
	model_t *handModel = R_LoadVrHandModel( true );
	if( !handModel || handModel->type != mod_studio )
		return;

	vec3_t dummyOrigin, dummyAngles;
	if( !XR_GetHandPresenceTransform( R_VR_PrimaryHandIndex(), dummyOrigin, dummyAngles ) )
		return;

	R_DrawHandEntity( &s_primaryHandEnt, handModel );
}

/*
====================
R_VR_DrawHandsLayer

Draws the persistent 6DoF hand presence layer. Returns true when the layer
owns hand rendering for this frame, so the legacy viewmodel path does not
draw the hands a second time.
====================
*/
static qboolean R_VR_DrawHandsLayer( void )
{
	static cvar_t *vr_hands_always_visible = NULL;
	if( !vr_hands_always_visible ) vr_hands_always_visible = gEngfuncs.pfnGetCvarPointer( "vr_hands_always_visible" );

	if( !XR_IsActive() || !vr_hands_always_visible || vr_hands_always_visible->value <= 0.0f )
		return false;

	static cvar_t *vr_hand_death_visible = NULL;
	if( !vr_hand_death_visible ) vr_hand_death_visible = gEngfuncs.pfnGetCvarPointer( "vr_hand_death_visible" );

	qboolean dead = ( ENGINE_GET_PARM( PARM_LOCAL_HEALTH ) <= 0 );
	if( dead && ( !vr_hand_death_visible || vr_hand_death_visible->value <= 0.0f ))
		return false;

	// Third-person / camera views place the hands in front of the editor
	// camera instead of the player, so keep the legacy behaviour there.
	if( FBitSet( RI.rvp.flags, RF_DRAW_CUBEMAP ) || ENGINE_GET_PARM( PARM_THIRDPERSON ) || !CL_IsViewEntityLocalPlayer( ))
		return false;

	if( !R_VR_WeaponTrueDepth() )
		pglDepthRange( gldepthmin, gldepthmin + VIEWMODEL_DEPTH_RANGE * ( gldepthmax - gldepthmin ));

	// The weapon viewmodel carries the primary hand mesh whenever a studio
	// viewmodel is actually drawn; otherwise render the standalone empty hand.
	cl_entity_t *view = tr.viewent;
	qboolean weapon_drawn = ( !dead && view && view->model && view->model->type == mod_studio && r_drawviewmodel->value != 0.0f );

	// vr_hide_arms >= 2 strips the glove/hand meshes off the weapon viewmodel,
	// so the viewmodel no longer supplies a hand and the standalone hand must
	// take over even while a weapon is held.
	static cvar_t *vr_hide_arms = NULL;
	if( !vr_hide_arms ) vr_hide_arms = gEngfuncs.pfnGetCvarPointer( "vr_hide_arms" );
	qboolean weapon_hides_hand = ( vr_hide_arms && vr_hide_arms->value >= 2.0f );

	if( weapon_hides_hand || !weapon_drawn )
	{
		if( weapon_drawn && weapon_hides_hand )
			gEngfuncs.Con_DPrintf( "[VR_HANDS_DBG] Weapon hand hidden by vr_hide_arms, drawing standalone primary hand\n" );
		R_DrawPrimaryHand();
	}

	// Two-handed suppression only makes sense while the viewmodel still owns the
	// supporting hand; once its hands are stripped, draw the off-hand as well.
	if( !weapon_drawn || weapon_hides_hand || !R_VR_OffHandAttachedToWeapon( ))
		R_DrawOffHand();

	pglDepthRange( gldepthmin, gldepthmax );

	return true;
}

/*
====================
R_StudioDrawVRDebugHand

Renders a 6DoF physical controller tracking wireframe, RGB coordinate axes,
grip offset connection vector, and muzzle alignment ray to calibrate .mdl models.
====================
*/
/*
====================
R_VR_DrawDebugCircle

Renders a 3D circle/ring in space given center and two orthogonal basis vectors.
====================
*/
static void R_VR_DrawDebugCircle( const vec3_t center, const vec3_t v1, const vec3_t v2, float radius, int segments )
{
	pglBegin( GL_LINE_LOOP );
	for( int i = 0; i < segments; i++ )
	{
		float theta = (float)i * (2.0f * (float)M_PI / (float)segments);
		float ct = cosf( theta );
		float st = sinf( theta );
		pglVertex3f( center[0] + (v1[0] * ct + v2[0] * st) * radius,
		             center[1] + (v1[1] * ct + v2[1] * st) * radius,
		             center[2] + (v1[2] * ct + v2[2] * st) * radius );
	}
	pglEnd();
}

/*
====================
R_StudioDrawVRDebugHand

Renders 3D coordinate points for primary and secondary hands, computes and displays
the weapon Center of Mass (COM), draws oriented 3D hitboxes, and continuously reports
head/hand/weapon coordinates on the HUD.
====================
*/
static void R_StudioDrawVRDebugHand( cl_entity_t *view )
{
	static cvar_t *vr_debug_hand = NULL;
	if( !vr_debug_hand ) vr_debug_hand = gEngfuncs.pfnGetCvarPointer( "vr_debug_hand" );
	if( !vr_debug_hand || vr_debug_hand->value <= 0.0f )
		return;

	if( !s_vrDebugHandActive )
		return;

	// Ensure secondary hand tracking is continuously active and updated
	vec3_t secHandOrigin, secHandAngles;
	if( XR_GetSecondaryHandTransform( secHandOrigin, secHandAngles ) )
	{
		float scale = (vr_worldscale && vr_worldscale->value > 0.0f) ? vr_worldscale->value : 40.0f;
		float turn_yaw = XR_GetPlayerTurnYaw();
		float cy = cosf( turn_yaw * (M_PI / 180.0f) );
		float sy = sinf( turn_yaw * (M_PI / 180.0f) );

		float world_dx = (secHandOrigin[0] * cy - secHandOrigin[1] * sy) * scale;
		float world_dy = (secHandOrigin[0] * sy + secHandOrigin[1] * cy) * scale;
		float world_dz = secHandOrigin[2] * scale;

		s_vrDebugOffHandOrigin[0] = RI.rvp.vieworigin[0] + world_dx;
		s_vrDebugOffHandOrigin[1] = RI.rvp.vieworigin[1] + world_dy;
		s_vrDebugOffHandOrigin[2] = RI.rvp.vieworigin[2] + world_dz;

		s_vrDebugOffHandAngles[0] = secHandAngles[0];
		s_vrDebugOffHandAngles[1] = anglemod( secHandAngles[1] + turn_yaw );
		s_vrDebugOffHandAngles[2] = secHandAngles[2];
		s_vrDebugOffHandActive = true;
	}

	pglDisable( GL_TEXTURE_2D );
	pglDisable( GL_DEPTH_TEST );
	pglEnable( GL_BLEND );
	pglBlendFunc( GL_SRC_ALPHA, GL_ONE );

	// 1. Primary Hand 6DoF Pose & Coordinate Axes
	vec3_t h_fwd, h_rt, h_up;
	AngleVectors( s_vrDebugRawHandAngles, h_fwd, h_rt, h_up );

	float axis_len = 5.0f;

	// Red: +Forward (Aim vector)
	pglLineWidth( 3.0f );
	pglColor4f( 1.0f, 0.15f, 0.15f, 0.95f );
	pglBegin( GL_LINES );
	pglVertex3fv( s_vrDebugRawHandOrigin );
	pglVertex3f( s_vrDebugRawHandOrigin[0] + h_fwd[0] * (axis_len * 1.5f),
	             s_vrDebugRawHandOrigin[1] + h_fwd[1] * (axis_len * 1.5f),
	             s_vrDebugRawHandOrigin[2] + h_fwd[2] * (axis_len * 1.5f) );
	pglEnd();

	// Green: +Right
	pglLineWidth( 2.5f );
	pglColor4f( 0.15f, 1.0f, 0.15f, 0.95f );
	pglBegin( GL_LINES );
	pglVertex3fv( s_vrDebugRawHandOrigin );
	pglVertex3f( s_vrDebugRawHandOrigin[0] + h_rt[0] * axis_len,
	             s_vrDebugRawHandOrigin[1] + h_rt[1] * axis_len,
	             s_vrDebugRawHandOrigin[2] + h_rt[2] * axis_len );
	pglEnd();

	// Blue: +Up
	pglLineWidth( 2.5f );
	pglColor4f( 0.2f, 0.5f, 1.0f, 0.95f );
	pglBegin( GL_LINES );
	pglVertex3fv( s_vrDebugRawHandOrigin );
	pglVertex3f( s_vrDebugRawHandOrigin[0] + h_up[0] * axis_len,
	             s_vrDebugRawHandOrigin[1] + h_up[1] * axis_len,
	             s_vrDebugRawHandOrigin[2] + h_up[2] * axis_len );
	pglEnd();

	// Primary Hand: 3D Coordinate Point Gizmo with Orthogonal Gyro Rings
	pglLineWidth( 2.0f );
	pglColor4f( 0.0f, 0.9f, 1.0f, 0.85f ); // Cyan gyro rings
	R_VR_DrawDebugCircle( s_vrDebugRawHandOrigin, h_rt, h_up, 1.5f, 16 );
	R_VR_DrawDebugCircle( s_vrDebugRawHandOrigin, h_fwd, h_up, 1.5f, 16 );
	R_VR_DrawDebugCircle( s_vrDebugRawHandOrigin, h_fwd, h_rt, 1.5f, 16 );

	// Coordinate Point Crosshair at Primary Hand Origin
	pglLineWidth( 2.5f );
	pglColor4f( 1.0f, 1.0f, 1.0f, 0.95f ); // White center dot cross
	float pCross = 0.8f;
	pglBegin( GL_LINES );
	pglVertex3f( s_vrDebugRawHandOrigin[0] - h_rt[0] * pCross, s_vrDebugRawHandOrigin[1] - h_rt[1] * pCross, s_vrDebugRawHandOrigin[2] - h_rt[2] * pCross );
	pglVertex3f( s_vrDebugRawHandOrigin[0] + h_rt[0] * pCross, s_vrDebugRawHandOrigin[1] + h_rt[1] * pCross, s_vrDebugRawHandOrigin[2] + h_rt[2] * pCross );
	pglVertex3f( s_vrDebugRawHandOrigin[0] - h_up[0] * pCross, s_vrDebugRawHandOrigin[1] - h_up[1] * pCross, s_vrDebugRawHandOrigin[2] - h_up[2] * pCross );
	pglVertex3f( s_vrDebugRawHandOrigin[0] + h_up[0] * pCross, s_vrDebugRawHandOrigin[1] + h_up[1] * pCross, s_vrDebugRawHandOrigin[2] + h_up[2] * pCross );
	pglEnd();

	// Physical Controller Handle Wireframe Box (Touch Plus palm center)
	float f_min = -3.5f, f_max = 1.5f;
	float r_min = -1.2f, r_max = 1.2f;
	float u_min = -4.0f, u_max = 1.5f;

	vec3_t box[8];
	for( int i = 0; i < 8; i++ )
	{
		float sf = (i & 1) ? f_max : f_min;
		float sr = (i & 2) ? r_max : r_min;
		float su = (i & 4) ? u_max : u_min;
		box[i][0] = s_vrDebugRawHandOrigin[0] + h_fwd[0] * sf + h_rt[0] * sr + h_up[0] * su;
		box[i][1] = s_vrDebugRawHandOrigin[1] + h_fwd[1] * sf + h_rt[1] * sr + h_up[1] * su;
		box[i][2] = s_vrDebugRawHandOrigin[2] + h_fwd[2] * sf + h_rt[2] * sr + h_up[2] * su;
	}

	static const int edges[12][2] = {
		{0, 1}, {2, 3}, {4, 5}, {6, 7}, // fwd
		{0, 2}, {1, 3}, {4, 6}, {5, 7}, // rt
		{0, 4}, {1, 5}, {2, 6}, {3, 7}  // up
	};

	pglLineWidth( 1.8f );
	pglColor4f( 0.0f, 0.9f, 1.0f, 0.65f ); // Cyan wireframe controller
	pglBegin( GL_LINES );
	for( int e = 0; e < 12; e++ )
	{
		pglVertex3fv( box[edges[e][0]] );
		pglVertex3fv( box[edges[e][1]] );
	}
	pglEnd();

	// Calculate Weapon Center of Mass (COM)
	vec3_t weapon_com = {0, 0, 0};
	int num_hitboxes = (m_pStudioHeader ? m_pStudioHeader->numhitboxes : 0);
	if( num_hitboxes > 0 )
	{
		float total_vol = 0.0f;
		mstudiobbox_t *pbbox = (mstudiobbox_t *)((byte *)m_pStudioHeader + m_pStudioHeader->hitboxindex);
		for( int i = 0; i < num_hitboxes; i++ )
		{
			vec3_t hb_mid, hb_world;
			hb_mid[0] = (pbbox[i].bbmin[0] + pbbox[i].bbmax[0]) * 0.5f;
			hb_mid[1] = (pbbox[i].bbmin[1] + pbbox[i].bbmax[1]) * 0.5f;
			hb_mid[2] = (pbbox[i].bbmin[2] + pbbox[i].bbmax[2]) * 0.5f;
			Matrix3x4_VectorTransform( g_studio.bonestransform[pbbox[i].bone], hb_mid, hb_world );

			float dx = fabsf( pbbox[i].bbmax[0] - pbbox[i].bbmin[0] );
			float dy = fabsf( pbbox[i].bbmax[1] - pbbox[i].bbmin[1] );
			float dz = fabsf( pbbox[i].bbmax[2] - pbbox[i].bbmin[2] );
			float vol = dx * dy * dz;
			if( vol <= 0.01f ) vol = 1.0f;

			VectorMA( weapon_com, vol, hb_world, weapon_com );
			total_vol += vol;
		}
		if( total_vol > 0.0f )
			VectorScale( weapon_com, 1.0f / total_vol, weapon_com );
		else if( view )
			VectorCopy( view->origin, weapon_com );
	}
	else if( m_pStudioHeader )
	{
		vec3_t bb_mid;
		bb_mid[0] = (m_pStudioHeader->bbmin[0] + m_pStudioHeader->bbmax[0]) * 0.5f;
		bb_mid[1] = (m_pStudioHeader->bbmin[1] + m_pStudioHeader->bbmax[1]) * 0.5f;
		bb_mid[2] = (m_pStudioHeader->bbmin[2] + m_pStudioHeader->bbmax[2]) * 0.5f;
		Matrix3x4_VectorTransform( g_studio.bonestransform[0], bb_mid, weapon_com );
	}
	else if( view )
	{
		VectorCopy( view->origin, weapon_com );
	}

	// Cache telemetry snapshot
	VectorCopy( weapon_com, s_vrDebugWeaponCOM );
	s_vrDebugNumHitboxes = num_hitboxes;
	if( view && view->model && view->model->name[0] )
		Q_strncpy( s_vrDebugWeaponModelName, view->model->name, sizeof( s_vrDebugWeaponModelName ) );
	if( view && !VectorIsNull( view->attachment[0] ) )
		VectorCopy( view->attachment[0], s_vrDebugMuzzlePos );
	else if( view )
		VectorCopy( view->origin, s_vrDebugMuzzlePos );

	// 2. Weapon Origin, Center of Mass (COM), and Barrel Rays
	if( view && view->model )
	{
		// Yellow Offset Guide Vector: Real Hand Pose -> Weapon Model Origin
		pglLineWidth( 2.5f );
		pglColor4f( 1.0f, 0.9f, 0.1f, 0.95f ); // Bright Yellow
		pglBegin( GL_LINES );
		pglVertex3fv( s_vrDebugRawHandOrigin );
		pglVertex3fv( view->origin );
		pglEnd();

		// Diamond marker at weapon origin
		vec3_t w_fwd, w_rt, w_up;
		AngleVectors( view->angles, w_fwd, w_rt, w_up );

		float dR = 1.2f;
		pglLineWidth( 2.0f );
		pglColor4f( 1.0f, 0.6f, 0.0f, 0.9f ); // Orange diamond
		pglBegin( GL_LINE_LOOP );
		pglVertex3f( view->origin[0] + w_rt[0] * dR, view->origin[1] + w_rt[1] * dR, view->origin[2] + w_rt[2] * dR );
		pglVertex3f( view->origin[0] + w_up[0] * dR, view->origin[1] + w_up[1] * dR, view->origin[2] + w_up[2] * dR );
		pglVertex3f( view->origin[0] - w_rt[0] * dR, view->origin[1] - w_rt[1] * dR, view->origin[2] - w_rt[2] * dR );
		pglVertex3f( view->origin[0] - w_up[0] * dR, view->origin[1] - w_up[1] * dR, view->origin[2] - w_up[2] * dR );
		pglEnd();

		// Weapon Barrel Direction Ray (Magenta)
		pglLineWidth( 2.0f );
		pglColor4f( 1.0f, 0.2f, 0.8f, 0.85f ); // Magenta ray
		pglBegin( GL_LINES );
		pglVertex3fv( view->origin );
		pglVertex3f( view->origin[0] + w_fwd[0] * 18.0f,
		             view->origin[1] + w_fwd[1] * 18.0f,
		             view->origin[2] + w_fwd[2] * 18.0f );
		pglEnd();

		// 3. Weapon Center of Mass (COM) 3D Point Gizmo
		// Dual concentric gyro rings at COM (Gold)
		pglLineWidth( 2.2f );
		pglColor4f( 1.0f, 0.85f, 0.05f, 0.95f ); // Bright Gold
		R_VR_DrawDebugCircle( weapon_com, w_rt, w_up, 1.4f, 16 );
		R_VR_DrawDebugCircle( weapon_com, w_fwd, w_up, 1.4f, 16 );
		R_VR_DrawDebugCircle( weapon_com, w_fwd, w_rt, 1.4f, 16 );

		// 3D Crosshair at COM
		float com_cross = 1.8f;
		pglLineWidth( 2.5f );
		pglColor4f( 1.0f, 0.25f, 0.1f, 0.95f ); // Crimson/Orange cross
		pglBegin( GL_LINES );
		pglVertex3f( weapon_com[0] - w_rt[0] * com_cross, weapon_com[1] - w_rt[1] * com_cross, weapon_com[2] - w_rt[2] * com_cross );
		pglVertex3f( weapon_com[0] + w_rt[0] * com_cross, weapon_com[1] + w_rt[1] * com_cross, weapon_com[2] + w_rt[2] * com_cross );
		pglVertex3f( weapon_com[0] - w_up[0] * com_cross, weapon_com[1] - w_up[1] * com_cross, weapon_com[2] - w_up[2] * com_cross );
		pglVertex3f( weapon_com[0] + w_up[0] * com_cross, weapon_com[1] + w_up[1] * com_cross, weapon_com[2] + w_up[2] * com_cross );
		pglVertex3f( weapon_com[0] - w_fwd[0] * com_cross, weapon_com[1] - w_fwd[1] * com_cross, weapon_com[2] - w_fwd[2] * com_cross );
		pglVertex3f( weapon_com[0] + w_fwd[0] * com_cross, weapon_com[1] + w_fwd[1] * com_cross, weapon_com[2] + w_fwd[2] * com_cross );
		pglEnd();

		// Moment-Arm Vector: Hand Tracking Point -> Weapon COM
		pglLineWidth( 3.0f );
		pglColor4f( 1.0f, 0.85f, 0.05f, 0.95f ); // Gold line
		pglBegin( GL_LINES );
		pglVertex3fv( s_vrDebugRawHandOrigin );
		pglVertex3fv( weapon_com );
		pglEnd();

		// 4. Muzzle Attachment Indicator & Line of Fire (Neon Green)
		if( !VectorIsNull( view->attachment[0] ) )
		{
			vec3_t muz;
			VectorCopy( view->attachment[0], muz );

			// COM -> Muzzle Connection Vector
			pglLineWidth( 2.0f );
			pglColor4f( 0.3f, 1.0f, 0.3f, 0.85f ); // Lime Green
			pglBegin( GL_LINES );
			pglVertex3fv( weapon_com );
			pglVertex3fv( muz );
			pglEnd();

			// 3D Cross at muzzle
			float cR = 1.5f;
			pglLineWidth( 2.5f );
			pglColor4f( 0.2f, 1.0f, 0.2f, 0.95f );
			pglBegin( GL_LINES );
			pglVertex3f( muz[0] - w_rt[0] * cR, muz[1] - w_rt[1] * cR, muz[2] - w_rt[2] * cR );
			pglVertex3f( muz[0] + w_rt[0] * cR, muz[1] + w_rt[1] * cR, muz[2] + w_rt[2] * cR );
			pglVertex3f( muz[0] - w_up[0] * cR, muz[1] - w_up[1] * cR, muz[2] - w_up[2] * cR );
			pglVertex3f( muz[0] + w_up[0] * cR, muz[1] + w_up[1] * cR, muz[2] + w_up[2] * cR );
			pglEnd();

			// Muzzle Laser Sight Forward Ray
			pglLineWidth( 1.5f );
			pglColor4f( 0.2f, 1.0f, 0.4f, 0.60f );
			pglBegin( GL_LINES );
			pglVertex3fv( muz );
			pglVertex3f( muz[0] + w_fwd[0] * 96.0f,
			             muz[1] + w_fwd[1] * 96.0f,
			             muz[2] + w_fwd[2] * 96.0f );
			pglEnd();
		}
	}

	// 5. Secondary (Off-hand) Controller 3D Coordinate Point & Two-Hand Connection
	if( s_vrDebugOffHandActive )
	{
		vec3_t o_fwd, o_rt, o_up;
		AngleVectors( s_vrDebugOffHandAngles, o_fwd, o_rt, o_up );

		// Coordinate axes for off-hand
		pglLineWidth( 2.0f );
		pglColor4f( 1.0f, 0.5f, 0.2f, 0.85f ); // Amber/Orange
		pglBegin( GL_LINES );
		pglVertex3fv( s_vrDebugOffHandOrigin );
		pglVertex3f( s_vrDebugOffHandOrigin[0] + o_fwd[0] * 3.5f,
		             s_vrDebugOffHandOrigin[1] + o_fwd[1] * 3.5f,
		             s_vrDebugOffHandOrigin[2] + o_fwd[2] * 3.5f );
		pglVertex3fv( s_vrDebugOffHandOrigin );
		pglVertex3f( s_vrDebugOffHandOrigin[0] + o_rt[0] * 2.5f,
		             s_vrDebugOffHandOrigin[1] + o_rt[1] * 2.5f,
		             s_vrDebugOffHandOrigin[2] + o_rt[2] * 2.5f );
		pglVertex3fv( s_vrDebugOffHandOrigin );
		pglVertex3f( s_vrDebugOffHandOrigin[0] + o_up[0] * 2.5f,
		             s_vrDebugOffHandOrigin[1] + o_up[1] * 2.5f,
		             s_vrDebugOffHandOrigin[2] + o_up[2] * 2.5f );
		pglEnd();

		// Secondary Hand Gyro Rings in Amber
		pglLineWidth( 2.0f );
		pglColor4f( 1.0f, 0.6f, 0.1f, 0.85f );
		R_VR_DrawDebugCircle( s_vrDebugOffHandOrigin, o_rt, o_up, 1.5f, 16 );
		R_VR_DrawDebugCircle( s_vrDebugOffHandOrigin, o_fwd, o_up, 1.5f, 16 );
		R_VR_DrawDebugCircle( s_vrDebugOffHandOrigin, o_fwd, o_rt, 1.5f, 16 );

		// Guide line between primary and secondary hand
		pglLineWidth( 1.5f );
		pglColor4f( 0.8f, 0.8f, 0.8f, 0.50f );
		pglBegin( GL_LINES );
		pglVertex3fv( s_vrDebugRawHandOrigin );
		pglVertex3fv( s_vrDebugOffHandOrigin );
		pglEnd();
	}

	// 6. Draw 3D Hitbox Wireframe Cubes for all weapon model hitboxes (if vr_debug_hand >= 2)
	if( vr_debug_hand->value >= 2.0f && m_pStudioHeader && num_hitboxes > 0 )
	{
		mstudiobbox_t *pbbox = (mstudiobbox_t *)((byte *)m_pStudioHeader + m_pStudioHeader->hitboxindex);
		for( int i = 0; i < num_hitboxes; i++ )
		{
			vec3_t p[8];
			for( int j = 0; j < 8; j++ )
			{
				vec3_t tmp;
				tmp[0] = (j & 1) ? pbbox[i].bbmax[0] : pbbox[i].bbmin[0];
				tmp[1] = (j & 2) ? pbbox[i].bbmax[1] : pbbox[i].bbmin[1];
				tmp[2] = (j & 4) ? pbbox[i].bbmax[2] : pbbox[i].bbmin[2];
				Matrix3x4_VectorTransform( g_studio.bonestransform[pbbox[i].bone], tmp, p[j] );
			}

			int grp = pbbox[i].group % 8;
			pglLineWidth( 1.5f );
			pglColor4f( hullcolor[grp][0], hullcolor[grp][1], hullcolor[grp][2], 0.85f );
			pglBegin( GL_LINES );
			for( int e = 0; e < 12; e++ )
			{
				pglVertex3fv( p[edges[e][0]] );
				pglVertex3fv( p[edges[e][1]] );
			}
			pglEnd();
		}

		R_StudioDrawBones();
		R_StudioDrawAttachments();
	}

	pglDisable( GL_BLEND );
	pglEnable( GL_DEPTH_TEST );
	pglEnable( GL_TEXTURE_2D );
	pglColor4f( 1.0f, 1.0f, 1.0f, 1.0f );

	// 7. Continuous Real-Time HUD Telemetry Reporting
	if( gEngfuncs.Con_NPrintf )
	{
		vec3_t head_pos = {0}, head_ang = {0};
		XR_GetHeadCenterTransform( head_pos, head_ang );
		vec3_t rhand_vel = {0};
		XR_GetPrimaryHandVelocity( rhand_vel );
		float speed_ms = VectorLength( rhand_vel );
		float hand_dist = (s_vrDebugOffHandActive ? VectorDistance( s_vrDebugRawHandOrigin, s_vrDebugOffHandOrigin ) : 0.0f);
		float grip_to_com = VectorDistance( s_vrDebugRawHandOrigin, weapon_com );
		qboolean is_twohanded = XR_IsTwoHandStabilized();

		gEngfuncs.Con_NPrintf( 0, "^2[VR 6DOF TELEMETRY] vr_debug_hand = %.0f (1=Gizmos+COM, 2=+Hitboxes+Skeleton)", vr_debug_hand->value );
		gEngfuncs.Con_NPrintf( 1, "^3HEAD:   Pos [%.1f, %.1f, %.1f] | Angles [P:%.1f, Y:%.1f, R:%.1f]",
			head_pos[0], head_pos[1], head_pos[2], head_ang[0], head_ang[1], head_ang[2] );
		gEngfuncs.Con_NPrintf( 2, "^5R-HAND: Pos [%.1f, %.1f, %.1f] | Angles [P:%.1f, Y:%.1f, R:%.1f] | Spd: %.2f m/s",
			s_vrDebugRawHandOrigin[0], s_vrDebugRawHandOrigin[1], s_vrDebugRawHandOrigin[2],
			s_vrDebugRawHandAngles[0], s_vrDebugRawHandAngles[1], s_vrDebugRawHandAngles[2], speed_ms );
		gEngfuncs.Con_NPrintf( 3, "^6L-HAND: Pos [%.1f, %.1f, %.1f] | Angles [P:%.1f, Y:%.1f, R:%.1f] | 2-Hand: %s (Dist: %.1f)",
			s_vrDebugOffHandOrigin[0], s_vrDebugOffHandOrigin[1], s_vrDebugOffHandOrigin[2],
			s_vrDebugOffHandAngles[0], s_vrDebugOffHandAngles[1], s_vrDebugOffHandAngles[2],
			is_twohanded ? "YES" : "NO", hand_dist );
		gEngfuncs.Con_NPrintf( 4, "^4WEAPON: %s | COM [%.1f, %.1f, %.1f] | Grip Dist: %.1f",
			(view && view->model && view->model->name[0]) ? view->model->name : "v_weapon",
			weapon_com[0], weapon_com[1], weapon_com[2], grip_to_com );
		gEngfuncs.Con_NPrintf( 5, "^7HITBOX: %d boxes | Muzzle [%.1f, %.1f, %.1f]",
			num_hitboxes, s_vrDebugMuzzlePos[0], s_vrDebugMuzzlePos[1], s_vrDebugMuzzlePos[2] );
	}
}

/*
====================
R_VR_Telemetry_f

Console command handler that prints a full instantaneous 6DoF telemetry snapshot.
====================
*/
void R_VR_Telemetry_f( void )
{
	vec3_t head_pos = {0}, head_ang = {0};
	vec3_t rhand_pos = {0}, rhand_ang = {0};
	vec3_t lhand_pos = {0}, lhand_ang = {0};
	vec3_t rhand_vel = {0};

	XR_GetHeadCenterTransform( head_pos, head_ang );
	XR_GetPrimaryHandTransform( rhand_pos, rhand_ang );
	XR_GetPrimaryHandVelocity( rhand_vel );
	XR_GetSecondaryHandTransform( lhand_pos, lhand_ang );

	float hand_dist = VectorDistance( rhand_pos, lhand_pos );
	float grip_to_com = VectorDistance( rhand_pos, s_vrDebugWeaponCOM );
	float speed_ms = VectorLength( rhand_vel );

	gEngfuncs.Con_Printf( "\n^2==========================================================\n" );
	gEngfuncs.Con_Printf( "^2  XASH3D VR - REAL-TIME 6DOF TELEMETRY SNAPSHOT\n" );
	gEngfuncs.Con_Printf( "^2==========================================================\n" );
	gEngfuncs.Con_Printf( "^3[HEAD / HMD]^7\n" );
	gEngfuncs.Con_Printf( "  Origin:  [X: %8.2f, Y: %8.2f, Z: %8.2f]\n", head_pos[0], head_pos[1], head_pos[2] );
	gEngfuncs.Con_Printf( "  Angles:  [Pitch: %6.1f, Yaw: %6.1f, Roll: %6.1f]\n", head_ang[0], head_ang[1], head_ang[2] );
	gEngfuncs.Con_Printf( "^5[PRIMARY HAND (Dominant)]^7\n" );
	gEngfuncs.Con_Printf( "  Origin:  [X: %8.2f, Y: %8.2f, Z: %8.2f]\n", rhand_pos[0], rhand_pos[1], rhand_pos[2] );
	gEngfuncs.Con_Printf( "  Angles:  [Pitch: %6.1f, Yaw: %6.1f, Roll: %6.1f]\n", rhand_ang[0], rhand_ang[1], rhand_ang[2] );
	gEngfuncs.Con_Printf( "  Speed:   %6.2f m/s\n", speed_ms );
	gEngfuncs.Con_Printf( "^6[SECONDARY HAND (Off-hand)]^7\n" );
	gEngfuncs.Con_Printf( "  Origin:  [X: %8.2f, Y: %8.2f, Z: %8.2f]\n", lhand_pos[0], lhand_pos[1], lhand_pos[2] );
	gEngfuncs.Con_Printf( "  Angles:  [Pitch: %6.1f, Yaw: %6.1f, Roll: %6.1f]\n", lhand_ang[0], lhand_ang[1], lhand_ang[2] );
	gEngfuncs.Con_Printf( "  Hand Separation Distance: %.2f GoldSrc units\n", hand_dist );
	gEngfuncs.Con_Printf( "^4[WEAPON & CENTER OF MASS (COM)]^7\n" );
	gEngfuncs.Con_Printf( "  Active Model: %s\n", s_vrDebugWeaponModelName[0] ? s_vrDebugWeaponModelName : "(none)" );
	gEngfuncs.Con_Printf( "  COM Pos: [X: %8.2f, Y: %8.2f, Z: %8.2f]\n", s_vrDebugWeaponCOM[0], s_vrDebugWeaponCOM[1], s_vrDebugWeaponCOM[2] );
	gEngfuncs.Con_Printf( "  Muzzle:  [X: %8.2f, Y: %8.2f, Z: %8.2f]\n", s_vrDebugMuzzlePos[0], s_vrDebugMuzzlePos[1], s_vrDebugMuzzlePos[2] );
	gEngfuncs.Con_Printf( "  Grip -> COM Distance: %.2f GoldSrc units\n", grip_to_com );
	gEngfuncs.Con_Printf( "  Hitboxes Registered:  %d\n", s_vrDebugNumHitboxes );
	gEngfuncs.Con_Printf( "^2==========================================================\n\n" );
}
#endif

/*
=================
R_DrawViewModel
=================
*/
void R_DrawViewModel( void )
{
	cl_entity_t	*view = tr.viewent;
	qboolean	hands_drawn = false;

	R_GatherPlayerLight( view );

	static model_t *s_lastVmModel = (model_t *)-1;
	if( view->model != s_lastVmModel )
	{
		s_lastVmModel = view->model;
		gEngfuncs.Con_Printf( "^2[VM_DBG_CHANGE] viewmodel changed to: '%s' (health=%d)\n",
			(view && view->model) ? view->model->name : "NULL",
			(int)ENGINE_GET_PARM( PARM_LOCAL_HEALTH ) );
	}

#ifdef XASH_OPENXR
	// Persistent 6DoF hand presence runs before any viewmodel gating so hands
	// stay visible with r_drawviewmodel 0, empty hands or a fading weapon.
	hands_drawn = R_VR_DrawHandsLayer();
#endif

	if( r_drawviewmodel->value == 0 )
		return;

	if( ENGINE_GET_PARM( PARM_THIRDPERSON ))
		return;

	// ignore in thirdperson, camera view or client is died
	if( FBitSet( RI.rvp.flags, RF_DRAW_CUBEMAP ) || ENGINE_GET_PARM( PARM_LOCAL_HEALTH ) <= 0 || !CL_IsViewEntityLocalPlayer())
		return;

	tr.blend = CL_FxBlend( view ) / 255.0f;
	if( !R_ModelOpaque( view->curstate.rendermode ) && tr.blend <= 0.0f )
		return; // invisible ?

	RI.currententity = view;

	if( !RI.currententity->model )
	{
#ifdef XASH_OPENXR
		static cvar_t *vr_offhand_render = NULL;
		if( !vr_offhand_render ) vr_offhand_render = gEngfuncs.pfnGetCvarPointer( "vr_offhand_render" );
		if( !hands_drawn && XR_IsActive() && vr_offhand_render && vr_offhand_render->value > 0.0f )
		{
			if( !R_VR_WeaponTrueDepth() )
				pglDepthRange( gldepthmin, gldepthmin + VIEWMODEL_DEPTH_RANGE * ( gldepthmax - gldepthmin ));
			R_DrawOffHand();
			pglDepthRange( gldepthmin, gldepthmax );
		}
#endif
		return;
	}

	// Flat-screen GoldSrc keeps the viewmodel in front of walls by compressing
	// its depth range. In VR the weapon is a world-space object, so keep the
	// real depth range and let world geometry occlude it.
	if( !R_VR_WeaponTrueDepth() )
		pglDepthRange( gldepthmin, gldepthmin + VIEWMODEL_DEPTH_RANGE * ( gldepthmax - gldepthmin ));
	RI.currentmodel = RI.currententity->model;

	switch( RI.currententity->model->type )
	{
	case mod_alias:
		R_DrawAliasModel( RI.currententity );
		break;
	case mod_studio:
		R_StudioSetupTimings();
		R_StudioDrawModelInternal( RI.currententity, STUDIO_RENDER );
		break;
	}

#ifdef XASH_OPENXR
	static cvar_t *vr_offhand_render = NULL;
	if( !vr_offhand_render ) vr_offhand_render = gEngfuncs.pfnGetCvarPointer( "vr_offhand_render" );

	// Render independent 6DoF off-hand (secondary controller) ONLY when:
	// 1) the persistent hand layer did not already draw it
	// 2) vr_offhand_render is explicitly enabled (> 0)
	// 3) Player is not currently gripping the weapon two-handed
	if( !hands_drawn && XR_IsActive() && vr_offhand_render && vr_offhand_render->value > 0.0f && !s_twohanded_active )
	{
		R_DrawOffHand();
	}

	// 6DoF physical hand & weapon calibration visualizer (wireframe, RGB axes, offset ray)
	if( XR_IsActive() )
	{
		R_StudioDrawVRDebugHand( view );
	}
#endif

	// restore depth range
	pglDepthRange( gldepthmin, gldepthmax );
}

/*
====================
R_StudioLoadTexture

load model texture with unique name
====================
*/
static void R_StudioLoadTexture( model_t *mod, studiohdr_t *phdr, mstudiotexture_t *ptexture )
{
	int		flags = 0;
	char		texname[128], name[128], mdlname[128];
	texture_t		*tx = NULL;
	qboolean load_external = false;

	if( ptexture->flags & STUDIO_NF_NORMALMAP )
		flags |= (TF_NORMALMAP);

	// store some textures for remapping
	if( !Q_strnicmp( ptexture->name, "DM_Base", 7 ) || !Q_strnicmp( ptexture->name, "remap", 5 ))
	{
		char	val[6];

		int i = mod->numtextures;
		mod->textures = (texture_t **)Mem_Realloc( mod->mempool, mod->textures, ( i + 1 ) * sizeof( texture_t* ));
		int size = ptexture->width * ptexture->height + 768;
		tx = Mem_Calloc( mod->mempool, sizeof( *tx ) + size );
		mod->textures[i] = tx;

		// store ranges into anim_min, anim_max etc
		if( !Q_strnicmp( ptexture->name, "DM_Base", 7 ))
		{
			Q_strncpy( tx->name, "DM_Base", sizeof( tx->name ));
			tx->anim_min = PLATE_HUE_START; // topcolor start
			tx->anim_max = PLATE_HUE_END; // topcolor end
			// bottomcolor start always equal is (topcolor end + 1)
			tx->anim_total = SUIT_HUE_END;// bottomcolor end
		}
		else
		{
			Q_strncpy( tx->name, "DM_User", sizeof( tx->name )); // custom remapped
			Q_strncpy( val, ptexture->name + 7, 4 );
			tx->anim_min = bound( 0, Q_atoi( val ), 255 ); // topcolor start
			Q_strncpy( val, ptexture->name + 11, 4 );
			tx->anim_max = bound( 0, Q_atoi( val ), 255 ); // topcolor end
			// bottomcolor start always equal is (topcolor end + 1)
			Q_strncpy( val, ptexture->name + 15, 4 );
			tx->anim_total = bound( 0, Q_atoi( val ), 255 ); // bottomcolor end
		}

		tx->width = ptexture->width;
		tx->height = ptexture->height;

		// the pixels immediately follow the structures
		byte *pixels = (byte *)phdr + ptexture->index;
		memcpy( tx+1, pixels, size );

		ptexture->flags |= STUDIO_NF_COLORMAP;	// yes, this is colormap image
		flags |= TF_FORCE_COLOR;

		mod->numtextures++;	// done
	}

	Q_strncpy( mdlname, mod->name, sizeof( mdlname ));
	COM_FileBase( ptexture->name, name, sizeof( name ));
	COM_StripExtension( mdlname );

	if( FBitSet( ptexture->flags, STUDIO_NF_NOMIPS ))
		SetBits( flags, TF_NOMIPMAP );

	if( FBitSet( gp_host->features, ENGINE_IMPROVED_LINETRACE ) && FBitSet( ptexture->flags, STUDIO_NF_MASKED ))
		flags |= TF_KEEP_SOURCE; // Paranoia2 texture alpha-tracing

	// NOTE: colormaps must have the palette for properly work. Ignore them
	if( Mod_AllowMaterials( ) && !FBitSet( ptexture->flags, STUDIO_NF_COLORMAP ))
	{
		if( R_SearchForTextureReplacement( texname, sizeof( texname ), mdlname, "materials/%s/%s.tga", mdlname, name ))
		{
			int gl_texturenum = GL_LoadTexture( texname, NULL, 0, flags );
			R_TextureReplacementReport( mdlname, gl_texturenum, texname );
			if(( load_external = gl_texturenum != 0 ))
				ptexture->index = gl_texturenum;
		}
	}

	if( !load_external )
	{
		// NOTE: replace index with pointer to start of imagebuffer, ImageLib expected it
		gEngfuncs.Image_SetMDLPointer((byte *)phdr + ptexture->index);
		size_t size = sizeof( mstudiotexture_t ) + ptexture->width * ptexture->height + 768;

		// build the texname
		Q_snprintf( texname, sizeof( texname ), "#%s/%s.mdl", mdlname, name );
		ptexture->index = GL_LoadTexture( texname, (byte *)ptexture, size, flags );
	}

	if( !ptexture->index )
	{
		ptexture->index = tr.defaultTexture;
	}
	else if( tx )
	{
		// duplicate texnum for easy acess
		tx->gl_texturenum = ptexture->index;
	}
}

/*
=================
Mod_StudioLoadTextures
=================
*/
void Mod_StudioLoadTextures( model_t *mod, void *data )
{
	studiohdr_t	*phdr = (studiohdr_t *)data;

	if( !phdr )
		return;

	mstudiotexture_t *ptexture = (mstudiotexture_t *)(((byte *)phdr) + phdr->textureindex);
	if( phdr->textureindex > 0 )
	{
		for( int i = 0; i < phdr->numtextures; i++ )
			R_StudioLoadTexture( mod, phdr, &ptexture[i] );
	}
}

/*
=================
Mod_StudioUnloadTextures
=================
*/
void Mod_StudioUnloadTextures( void *data )
{
	studiohdr_t	*phdr = (studiohdr_t *)data;

	if( !phdr )
		return;

	mstudiotexture_t *ptexture = (mstudiotexture_t *)(((byte *)phdr) + phdr->textureindex);

	// release all textures
	for( int i = 0; i < phdr->numtextures; i++ )
	{
		if( ptexture[i].index == tr.defaultTexture )
			continue;
		GL_FreeTexture( ptexture[i].index );
	}
}

static void pfnStudioDynamicLight( cl_entity_t *ent, alight_t *plight )
{
	R_EntityDynamicLight( ent, plight, FBitSet( RI.rvp.flags, RF_DRAW_WORLD ), g_studio.time, g_studio.lightspot, g_studio.lightvec );
}

qboolean R_StudioFillAPI( engine_studio_api_t *api, r_studio_interface_t *pDefaultDraw )
{
	cl_righthand = gEngfuncs.pfnGetCvarPointer( "cl_righthand" );

	api->GetCurrentEntity        = pfnGetCurrentEntity;
	api->PlayerInfo              = pfnPlayerInfo;
	api->GetPlayerState          = R_StudioGetPlayerState;
	api->GetTimes                = pfnGetEngineTimes;
	api->GetViewInfo             = pfnGetViewInfo;
	api->GetModelCounters        = pfnGetModelCounters;
	api->StudioGetBoneTransform  = pfnStudioGetBoneTransform;
	api->StudioGetLightTransform = pfnStudioGetLightTransform;
	api->StudioGetRotationMatrix = pfnStudioGetRotationMatrix;
	api->StudioSetupModel        = R_StudioSetupModel;
	api->StudioCheckBBox         = R_StudioCheckBBox;
	api->StudioDynamicLight      = pfnStudioDynamicLight;
	api->StudioEntityLight       = R_StudioEntityLight;
	api->StudioSetupLighting     = R_StudioSetupLighting;
	api->StudioDrawPoints        = R_StudioDrawPoints;
	api->StudioDrawHulls         = R_StudioDrawHulls;
	api->StudioDrawAbsBBox       = R_StudioDrawAbsBBox;
	api->StudioDrawBones         = R_StudioDrawBones;
	api->StudioSetupSkin         = (void *)R_StudioSetupSkin;
	api->StudioSetRemapColors    = R_StudioSetRemapColors;
	api->SetupPlayerModel        = R_StudioSetupPlayerModel;
	api->StudioClientEvents      = R_StudioClientEvents;
	api->GetForceFaceFlags       = R_StudioGetForceFaceFlags;
	api->SetForceFaceFlags       = R_StudioSetForceFaceFlags;
	api->StudioSetHeader         = (void *)R_StudioSetHeader;
	api->SetRenderModel          = R_StudioSetRenderModel;
	api->SetupRenderer           = R_StudioSetupRenderer;
	api->RestoreRenderer         = R_StudioRestoreRenderer;
	api->SetChromeOrigin         = R_StudioSetChromeOrigin;
	api->GL_StudioDrawShadow     = GL_StudioDrawShadow;
	api->GL_SetRenderMode        = GL_StudioSetRenderMode;
	api->StudioSetRenderamt      = R_StudioSetRenderamt;
	api->StudioSetCullState      = R_StudioSetCullState;
	api->StudioRenderShadow      = R_StudioRenderShadow;

	pDefaultDraw->version         = STUDIO_INTERFACE_VERSION;
	pDefaultDraw->StudioDrawModel  = R_StudioDrawModel;
	pDefaultDraw->StudioDrawPlayer = R_StudioDrawPlayer;

	return true;
}

void R_StudioSetDrawInterface( r_studio_interface_t *pDraw )
{
	pStudioDraw = pDraw;
}
