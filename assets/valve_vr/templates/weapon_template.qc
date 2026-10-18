// ==============================================================================
// Xash3D VR — GoldSrc Viewmodel QC Template for Modders & Content Creators
// ==============================================================================
// Use this template with Valve's studiomdl (GoldSrc v10) to compile viewmodels
// that natively support 6DoF tracking, muzzle ballistics, two-handed grips,
// and manual reloading in Xash3D VR.
// ==============================================================================

$modelname "v_custom_weapon.mdl"
$cd "./"
$cdtexture "./textures/"
$scale 1.0
$cliptotextures

// Root body mesh (Ensure closed 360 geometry with backfaces and right-side modeled)
$bodygroup "weapon"
{
    studio "custom_weapon_mesh"
}

// Optional: Isolated magazine mesh for manual reloading
// If separated, the engine can animate or physicalize the magazine drop
$bodygroup "magazine"
{
    studio "custom_weapon_mag"
    blank
}

// ==============================================================================
// VR ATTACHMENT CONVENTIONS (Xash3D VR Standard)
// ==============================================================================
// Attachment 0: MUZZLE
// - Purpose: Laser sight emission, server-side bullet traces, flash and tracers
// - Position: Tip of the barrel pointing in the firing direction (+Y forward)
$attachment 0 "gun_barrel" 0.000000 14.500000 2.200000

// Attachment 1: TWO-HANDED STABILIZATION GRIP ZONE
// - Purpose: Snaps or validates the secondary (off-hand) controller position
// - Position: Foregrip / handguard / pump where the secondary hand grips
$attachment 1 "gun_body" 0.000000 7.000000 -1.500000

// Attachment 2: BRASS EJECTION PORT
// - Purpose: Where spent bullet casings fly out in 3D roomspace
$attachment 2 "gun_slide" 1.200000 2.500000 1.800000

// Attachment 3: MAGAZINE WELL / RELOAD INSERTION POINT
// - Purpose: Proximity trigger zone for inserting fresh magazines in manual reload
$attachment 3 "gun_handle" 0.000000 -1.000000 -4.500000

// ==============================================================================
// SKELETON / BONE HIERARCHY
// ==============================================================================
// Recommended bone structure:
//   "root"              - Origin aligned with controller wrist/palm
//     └─ "gun_body"     - Main receiver
//         ├─ "gun_barrel"   (Parent of Attachment 0)
//         ├─ "gun_slide"    (Animates back on recoil, parent of Attachment 2)
//         ├─ "gun_trigger"  (Can be rotated by trigger analog axis)
//         └─ "gun_mag"      (Detachable magazine, parent of Attachment 3)

// Hitbox definitions
$hbox 0 "gun_body" -2.5 -5.0 -3.0 2.5 16.0 4.0

// Base animations
$sequence "idle" "anim_idle" fps 16 loop
$sequence "shoot" "anim_shoot" fps 30 { event 5001 0 "1" }
$sequence "reload" "anim_reload" fps 30 { event 5004 12 "weapons/custom_magout.wav" }
$sequence "draw" "anim_draw" fps 30
