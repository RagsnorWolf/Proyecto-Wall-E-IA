# rebuild_walle_rig.py
# Reconstruye el rig mecánico de WALL-E desde walle_animated.glb
# y exporta walle_fixed_v2.glb con las acciones Idle, Wave, Walk, Dance.
#
# Ejecutar dentro de Blender (pestaña Scripting > Run Script).

import bpy
from mathutils import Vector, Euler
import math


def clean_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat)
    for tex in list(bpy.data.textures):
        bpy.data.textures.remove(tex)
    for img in list(bpy.data.images):
        bpy.data.images.remove(img)
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)
    for arm in list(bpy.data.armatures):
        bpy.data.armatures.remove(arm)


SOURCE_GLB = r"E:\Proyectos Ragsnor\Proyecto Wall - E\wall-e-companion\Pagina Web\cockpit\ui\public\models\walle_animated.glb"
OUTPUT_GLB = r"E:\Proyectos Ragsnor\Proyecto Wall - E\wall-e-companion\Pagina Web\cockpit\ui\public\models\walle_fixed_v2.glb"


MESH_TO_BONE = {
    "body_low": "Body", "back_low": "Body", "base_low": "Body",
    "neck_low": "Neck", "eyes_low": "Head", "eyes_low.001": "Head",
    "hand_low": "Arm_R", "hand_low.001": "Arm_L", "hand_low.002": "Arm_R",
    "trackGears1_low": "Tread_R", "trackDetails001_low": "Tread_R", "trackGears4_low": "Tread_R",
    "track_low": "Tread_R", "track_low.001": "Tread_R", "track_low.002": "Tread_R",
    "track_low.003": "Tread_R", "track_low.004": "Tread_R", "track_low.006": "Tread_R",
    "track_low.007": "Tread_R", "track_low.008": "Tread_R", "track_low.009": "Tread_R",
    "track_low.010": "Tread_R", "track_low.011": "Tread_R", "track_low.013": "Tread_R",
    "track_low.021": "Tread_R", "track_low.027": "Tread_R", "track_low.028": "Tread_R",
    "trackGears2_low": "Tread_L", "trackGears3_low": "Tread_L",
    "track_low.005": "Tread_L", "track_low.012": "Tread_L", "track_low.014": "Tread_L",
    "track_low.015": "Tread_L", "track_low.016": "Tread_L", "track_low.017": "Tread_L",
    "track_low.018": "Tread_L", "track_low.019": "Tread_L", "track_low.020": "Tread_L",
    "track_low.022": "Tread_L", "track_low.023": "Tread_L", "track_low.024": "Tread_L",
    "track_low.025": "Tread_L", "track_low.026": "Tread_L",
}


def build_armature(mesh_objs):
    armature_data = bpy.data.armatures.new("WalleRig")
    armature_obj = bpy.data.objects.new("WalleRig", armature_data)
    bpy.context.collection.objects.link(armature_obj)
    bpy.context.view_layer.objects.active = armature_obj

    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature_data.edit_bones

    bone_positions = {
        "Root":    (Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 0.3))),
        "Body":    (Vector((0.0, 0.138, 0.741)), Vector((0.0, 0.138, 1.2))),
        "Neck":    (Vector((0.0, 0.138, 2.822)), Vector((0.0, 0.223, 3.392))),
        "Head":    (Vector((0.0, 0.223, 3.392)), Vector((0.0, 0.323, 3.592))),
        "Arm_L":   (Vector((1.035, -0.621, 2.364)), Vector((1.535, -0.621, 2.364))),
        "Arm_R":   (Vector((-1.035, -0.863, 2.364)), Vector((-1.535, -0.863, 2.364))),
        "Tread_L": (Vector((0.0, -0.514, 0.789)), Vector((0.0, -0.514, 0.189))),
        "Tread_R": (Vector((0.0, 0.729, 1.049)), Vector((0.0, 0.729, 0.449))),
    }

    created = {}
    for name, (head, tail) in bone_positions.items():
        eb = edit_bones.new(name)
        eb.head = head
        eb.tail = tail
        created[name] = eb

    created["Body"].parent = created["Root"]
    created["Neck"].parent = created["Body"]
    created["Head"].parent = created["Neck"]
    created["Arm_L"].parent = created["Body"]
    created["Arm_R"].parent = created["Body"]
    created["Tread_L"].parent = created["Body"]
    created["Tread_R"].parent = created["Body"]

    bpy.ops.object.mode_set(mode='OBJECT')

    for mesh_obj in mesh_objs:
        bone_name = MESH_TO_BONE.get(mesh_obj.name)
        if bone_name is None:
            continue
        mesh_obj.parent = armature_obj
        mesh_obj.parent_type = 'BONE'
        mesh_obj.parent_bone = bone_name

    return armature_obj, armature_data


def keyframe_pose(pose_bones, bone_name, data_path, index, frame, value):
    pb = pose_bones[bone_name]
    bpy.context.scene.frame_set(frame)
    if index is None:
        setattr(pb, data_path, value)
    else:
        current = getattr(pb, data_path)
        current[index] = value
        setattr(pb, data_path, current)
    pb.keyframe_insert(data_path=data_path, index=index)


def create_idle(pose_bones, armature_data):
    action = ensure_action(armature_data, "Idle")
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 48

    # Cuerpo: rebote vertical leve (Z)
    keyframe_pose(pose_bones, "Body", "location", 2, 1, 0.004)
    keyframe_pose(pose_bones, "Body", "location", 2, 24, -0.004)
    keyframe_pose(pose_bones, "Body", "location", 2, 48, 0.004)


def create_walk(pose_bones, armature_data):
    action = ensure_action(armature_data, "Walk")
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 48

    # Cuerpo: bob vertical
    keyframe_pose(pose_bones, "Body", "location", 2, 1, 0.035)
    keyframe_pose(pose_bones, "Body", "location", 2, 24, -0.035)
    keyframe_pose(pose_bones, "Body", "location", 2, 48, 0.035)

    # Cuerpo: ligera inclinación hacia adelante (X)
    keyframe_pose(pose_bones, "Body", "rotation_euler", 0, 1, math.radians(4))
    keyframe_pose(pose_bones, "Body", "rotation_euler", 0, 24, math.radians(-4))
    keyframe_pose(pose_bones, "Body", "rotation_euler", 0, 48, math.radians(4))

    # Orugas: rotación continua 360° en X
    for bone_name in ["Tread_L", "Tread_R"]:
        pb = pose_bones[bone_name]
        bpy.context.scene.frame_set(1)
        pb.rotation_euler.x = 0.0
        pb.keyframe_insert(data_path="rotation_euler", index=0)
        bpy.context.scene.frame_set(48)
        pb.rotation_euler.x = math.radians(360)
        pb.keyframe_insert(data_path="rotation_euler", index=0)


def create_wave(pose_bones, armature_data):
    action = ensure_action(armature_data, "Wave")
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 48

    # Brazo derecho: elevar 90° en X
    keyframe_pose(pose_bones, "Arm_R", "rotation_euler", 0, 1, 0.0)
    keyframe_pose(pose_bones, "Arm_R", "rotation_euler", 0, 18, math.radians(90))
    keyframe_pose(pose_bones, "Arm_R", "rotation_euler", 0, 30, math.radians(90))
    keyframe_pose(pose_bones, "Arm_R", "rotation_euler", 0, 48, 0.0)


def create_dance(pose_bones, armature_data):
    action = ensure_action(armature_data, "Dance")
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 48

    # Cuerpo: giro Z (-20° a 20°)
    keyframe_pose(pose_bones, "Body", "rotation_euler", 2, 1, math.radians(-20))
    keyframe_pose(pose_bones, "Body", "rotation_euler", 2, 24, math.radians(20))
    keyframe_pose(pose_bones, "Body", "rotation_euler", 2, 48, math.radians(-20))

    # Cuello: sacudida lateral (Y)
    keyframe_pose(pose_bones, "Neck", "rotation_euler", 1, 1, math.radians(-12))
    keyframe_pose(pose_bones, "Neck", "rotation_euler", 1, 24, math.radians(12))
    keyframe_pose(pose_bones, "Neck", "rotation_euler", 1, 48, math.radians(-12))

    # Cabeza: reacción (Y)
    keyframe_pose(pose_bones, "Head", "rotation_euler", 1, 1, math.radians(-5))
    keyframe_pose(pose_bones, "Head", "rotation_euler", 1, 24, math.radians(5))
    keyframe_pose(pose_bones, "Head", "rotation_euler", 1, 48, math.radians(-5))

    # Brazos opuestos (Y)
    keyframe_pose(pose_bones, "Arm_L", "rotation_euler", 1, 1, math.radians(10))
    keyframe_pose(pose_bones, "Arm_R", "rotation_euler", 1, 1, math.radians(-10))
    keyframe_pose(pose_bones, "Arm_L", "rotation_euler", 1, 24, math.radians(-10))
    keyframe_pose(pose_bones, "Arm_R", "rotation_euler", 1, 24, math.radians(10))
    keyframe_pose(pose_bones, "Arm_L", "rotation_euler", 1, 48, math.radians(10))
    keyframe_pose(pose_bones, "Arm_R", "rotation_euler", 1, 48, math.radians(-10))


_action_cache = {}


def ensure_action(armature_data, name):
    if name in _action_cache:
        return _action_cache[name]
    if name in bpy.data.actions:
        action = bpy.data.actions[name]
    else:
        action = bpy.data.actions.new(name)
    if armature_data.animation_data is None:
        armature_data.animation_data_create()
    armature_data.animation_data.action = action
    _action_cache[name] = action
    return action


def main():
    print("[WALL-E rig] Iniciando reconstrucción del rig mecánico...")
    clean_scene()
    bpy.ops.import_scene.gltf(filepath=SOURCE_GLB)
    print("[WALL-E rig] Modelo fuente importado:", SOURCE_GLB)

    mesh_objs = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    print(f"[WALL-E rig] Mallas importadas: {len(mesh_objs)}")

    armature_obj, armature_data = build_armature(mesh_objs)
    print("[WALL-E rig] Armature creado con 8 huesos: Root, Body, Neck, Head, Arm_L, Arm_R, Tread_L, Tread_R")

    # Pasar a POSE mode para animar los huesos
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='POSE')
    pose_bones = armature_obj.pose.bones

    create_idle(pose_bones, armature_data)
    create_walk(pose_bones, armature_data)
    create_wave(pose_bones, armature_data)
    create_dance(pose_bones, armature_data)
    print("[WALL-E rig] Animaciones creadas: Idle, Walk, Wave, Dance")

    bpy.ops.export_scene.gltf(
        filepath=OUTPUT_GLB,
        export_format='GLB',
        export_yup=True,
        export_apply=False,
        export_animations=True,
    )
    print(f"[WALL-E rig] Exportado: {OUTPUT_GLB}")


if __name__ == "__main__":
    main()
