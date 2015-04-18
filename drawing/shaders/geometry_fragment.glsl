#version 140
#extension GL_ARB_explicit_attrib_location : require
#extension GL_ARB_explicit_uniform_location : require

uniform sampler2D tex;
uniform sampler2D normal_tex;
uniform sampler2D occlude_tex;
uniform sampler2D displace_tex;
uniform int using_textures;

in vec2 vs_displacement;
in vec2 vs_texcoord;
in vec2 vs_normal_coord;
in vec2 vs_occlude_coord;
in vec4 vs_colour;

layout(location = 0) out vec4 diffuse;
layout(location = 1) out vec4 normal;
layout(location = 2) out vec4 displacement;
layout(location = 3) out vec4 occlude;

void main()
{
    //displacement = mix(vs_position,vec3(1,1,1),0.99);
    if( 1 == using_textures ) {
        diffuse   = texture(tex, vs_texcoord)*vs_colour;
        vec3 normal_out = texture(normal_tex, vs_normal_coord).xyz;
        occlude = texture(occlude_tex, vs_occlude_coord);
        displacement = texture(displace_tex,vs_displacement);
        normal = vec4(normal_out,1);
        if(diffuse.a == 0.0 || normal.a == 0.0) {
            discard;
        }
    }
    else {
        diffuse = vs_colour;
        normal = vec4(0,0,0,1);
        occlude = vec4(0,0,0,0);
        displacement = vec4(0,0,0,0);
    }
}
