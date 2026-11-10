package su.xash.engine.util

import android.content.Context
import java.io.File
import java.io.IOException

/**
 * Test-map launch arguments and on-demand installation.
 *
 * The engine always starts with the base `valve` game directory, while the
 * APK bundles the VR overlay under `assets/valve_vr/`. The scale testbed is
 * copied into `<gamedir>/maps/` before launch so the map works on a fresh
 * install without running the deploy script first.
 */
object TestMaps {
	const val CROSSFIRE = "+sv_cheats 1 +deathmatch 1 +map crossfire"
	const val TESTBED = "+sv_cheats 1 +map testbed_scale"
	const val HAZARD = "+sv_cheats 1 +map t0a0"

	private const val BUNDLED_DIR = "valve_vr/maps"
	private const val TESTBED_MAP = "testbed_scale"

	/**
	 * Copy a bundled test map into the active game directory when the launch
	 * arguments request it. Returns true when the file is present afterwards.
	 */
	fun ensureBundledMap(ctx: Context, gameDir: File, extraArgs: String?): Boolean {
		if (extraArgs.isNullOrBlank() || !extraArgs.contains("+map $TESTBED_MAP"))
			return true
		return install(ctx, gameDir, TESTBED_MAP)
	}

	private fun install(ctx: Context, gameDir: File, map: String): Boolean {
		val mapsDir = File(gameDir, "maps")
		if (!mapsDir.exists() && !mapsDir.mkdirs())
			return false

		val dest = File(mapsDir, "$map.bsp")
		return try {
			ctx.assets.open("$BUNDLED_DIR/$map.bsp").use { input ->
				dest.outputStream().use { output -> input.copyTo(output) }
			}
			true
		} catch (e: IOException) {
			// The map may already be deployed from the host; keep the launch
			// going and let the engine report a missing map if it is absent.
			dest.exists()
		}
	}
}
