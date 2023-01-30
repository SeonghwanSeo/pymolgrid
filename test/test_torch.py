import os
from pymolgrid.torch import Voxelizer, RandomTransform
import numpy as np
import torch
from rdkit import Chem
import sys
try :
    from utils import draw_pse
    assert sys.argv[1] == '-y'
    pymol = True
except :
    draw_pse = (lambda *x, **kwargs: None)
    pymol = False

device = 'cpu'

voxelizer = Voxelizer(resolution=0.5, dimension=48, atom_scale=1.5, density='gaussian', \
                    channel_wise_radii=False) # Default
voxelizer_small = Voxelizer(0.5, 16, blockdim = 16) # 0.5, 48
voxelizer_hr = Voxelizer(0.4, 64, device=device)
transform = RandomTransform(random_translation=0.5, random_rotation=True)

voxelizer.to(device)
voxelizer_small.to(device)

""" LOAD DATA """
ligand_path = './10gs/ligand.sdf'
pocket_path = './10gs/pocket.pdb'

ligand_rdmol = Chem.SDMolSupplier(ligand_path)[0]
pocket_rdmol = Chem.MolFromPDBFile(pocket_path)

ligand_coords = ligand_rdmol.GetConformer().GetPositions()
ligand_center = ligand_coords.mean(axis=0)
pocket_coords = pocket_rdmol.GetConformer().GetPositions()
coords = np.concatenate([ligand_coords, pocket_coords], axis=0)
center = ligand_center

""" Atom Types """
print('# Test Atom Type #')
save_dir = 'result_type'
if pymol :
    os.system(f'mkdir -p {save_dir}')

ligand_channels = ['C', 'N', 'O', 'S']
pocket_channels = ['C', 'N', 'O', 'S']
num_ligand_channels = len(ligand_channels)
num_pocket_channels = len(pocket_channels)
num_channels = num_ligand_channels + num_pocket_channels
ligand_type_dict = {'C': 0, 'N': 1, 'O': 2, 'S': 3}
pocket_type_dict = {'C': 4, 'N': 5, 'O': 6, 'S': 7}
ligand_types = [ligand_type_dict[atom.GetSymbol()] for atom in ligand_rdmol.GetAtoms()]
pocket_types = [pocket_type_dict[atom.GetSymbol()] for atom in pocket_rdmol.GetAtoms()]
atom_types = ligand_types + pocket_types

channel_radii = np.ones((num_channels,))
channel_radii[:4] = 2.0
atom_radii = np.ones((coords.shape[0],))
atom_radii[100:] = 2.0

coords = voxelizer.asarray(coords, 'coords')
center = voxelizer.asarray(center, 'center')
atom_types = voxelizer.asarray(atom_types, 'type')
channel_radii = voxelizer.asarray(channel_radii, 'radii')
atom_radii = voxelizer.asarray(atom_radii, 'radii')

grid = voxelizer.get_empty_grid(num_channels)
grid_small = voxelizer_small.get_empty_grid(num_channels)
grid_hr = voxelizer_hr.get_empty_grid(num_channels)

ligand_grid, pocket_grid = torch.split(grid, (num_ligand_channels, num_pocket_channels))
ligand_grid_small, pocket_grid_small = torch.split(grid_small, (num_ligand_channels, num_pocket_channels))
ligand_grid_hr, pocket_grid_hr = torch.split(grid_hr, (num_ligand_channels, num_pocket_channels))

print('Test 1: Binary: False, Channel-Wise Radii: False, Density: Gaussian (Default)')
ref_grid = voxelizer.forward(coords, center, atom_types, radii=1.0)
out_grid = voxelizer.forward(coords, center, atom_types, radii=1.0, out=grid)
assert grid is out_grid, 'INPLACE FAILE'
assert (grid - ref_grid).abs_().less_(1e-5).all().item(), 'REPRODUCTION FAIL'
draw_pse(f'{save_dir}/ref.pse', ligand_rdmol, pocket_rdmol, ligand_grid, pocket_grid, \
        ligand_channels, pocket_channels, center, voxelizer.resolution)

print('Test 2: Small (One Block)')
voxelizer_small.forward(coords, center, atom_types, radii=1.0, out=grid_small)
draw_pse(f'{save_dir}/small.pse', ligand_rdmol, pocket_rdmol, ligand_grid_small, pocket_grid_small, \
        ligand_channels, pocket_channels, center, voxelizer_small.resolution)

print('Test 3: High Resolution')
voxelizer_hr.forward(coords, center, atom_types, radii=1.0, out=grid_hr)
draw_pse(f'{save_dir}/hr.pse', ligand_rdmol, pocket_rdmol, ligand_grid_hr, pocket_grid_hr, \
        ligand_channels, pocket_channels, center, voxelizer_hr.resolution)

print('Test 4: With Atom-wise Radii')
voxelizer.forward(coords, center, atom_types, atom_radii, out=grid)
draw_pse(f'{save_dir}/atom-wise.pse', ligand_rdmol, pocket_rdmol, ligand_grid, pocket_grid, \
        ligand_channels, pocket_channels, center, voxelizer.resolution)

print('Test 5: Channel-Wise Radii: True')
voxelizer.channel_wise_radii = True
voxelizer.forward(coords, center, atom_types, channel_radii, out=grid)
draw_pse(f'{save_dir}/channel-wise.pse', ligand_rdmol, pocket_rdmol, ligand_grid, pocket_grid, \
        ligand_channels, pocket_channels, center, voxelizer.resolution)
voxelizer.channel_wise_radii = False

print('Test 6: Binary: True')
voxelizer.density = 'binary'
voxelizer.forward(coords, center, atom_types, radii = 1.0, out=grid)
draw_pse(f'{save_dir}/binary.pse', ligand_rdmol, pocket_rdmol, ligand_grid, pocket_grid, \
        ligand_channels, pocket_channels, center, voxelizer.resolution)
voxelizer.density = 'gaussian'

print('Test 7: Random transform')
new_coords = transform.forward(coords, center)
voxelizer.forward(new_coords, center, atom_types, radii = 1.0, out=grid)
draw_pse(f'{save_dir}/transform.pse', ligand_rdmol, pocket_rdmol, ligand_grid, pocket_grid, \
        ligand_channels, pocket_channels, center, voxelizer.resolution, new_coords=new_coords)
print()

""" Vector """
print('# Test Atom Feature #')
save_dir = 'result_feature'
if pymol :
    os.system(f'mkdir -p {save_dir}')

ligand_channels = ['C', 'N', 'O', 'S', 'Aromatic']
pocket_channels = ['C', 'N', 'O', 'S', 'Aromatic']
num_ligand_channels = len(ligand_channels)
num_pocket_channels = len(pocket_channels)
num_channels = num_ligand_channels + num_pocket_channels

def get_features(atom, is_pocket) :
    res = [0] * 10
    idx = 5 if is_pocket else 0
    symbol = atom.GetSymbol()
    if symbol == 'C'        : res[idx+0] = 1
    elif symbol == 'N'      : res[idx+1] = 1
    elif symbol == 'O'      : res[idx+2] = 1
    elif symbol == 'S'      : res[idx+3] = 1
    if atom.GetIsAromatic() : res[idx+4] = 1
    return res
ligand_features = [get_features(atom, False) for atom in ligand_rdmol.GetAtoms()]
pocket_features = [get_features(atom, True) for atom in pocket_rdmol.GetAtoms()]
atom_features = ligand_features + pocket_features

channel_radii = np.ones((num_channels,))
channel_radii[:4] = 2.0
atom_radii = np.ones((coords.shape[0],))
atom_radii[100:] = 2.0

coords = voxelizer.asarray(coords, 'coords')
center = voxelizer.asarray(center, 'center')
atom_features = voxelizer.asarray(atom_features, 'feature')
channel_radii = voxelizer.asarray(channel_radii, 'radii')
atom_radii = voxelizer.asarray(atom_radii, 'radii')

grid = voxelizer.get_empty_grid(num_channels)
grid_small = voxelizer_small.get_empty_grid(num_channels)
grid_hr = voxelizer_hr.get_empty_grid(num_channels)

ligand_grid, pocket_grid = torch.split(grid, (num_ligand_channels, num_pocket_channels))
ligand_grid_small, pocket_grid_small = torch.split(grid_small, (num_ligand_channels, num_pocket_channels))
ligand_grid_hr, pocket_grid_hr = torch.split(grid_hr, (num_ligand_channels, num_pocket_channels))

print('Test 1: Binary: False, Channel-Wise Radii: False, Density: Gaussian (Default)')
ref_grid = voxelizer.forward(coords, center, atom_features, radii=1.0)
out_grid = voxelizer.forward(coords, center, atom_features, radii=1.0, out=grid)
assert grid is out_grid, 'INPLACE FAILE'
assert (grid - ref_grid).abs_().less_(1e-5).all().item(), 'REPRODUCTION FAIL'
draw_pse(f'{save_dir}/ref.pse', ligand_rdmol, pocket_rdmol, ligand_grid, pocket_grid, \
        ligand_channels, pocket_channels, center, voxelizer.resolution)

print('Test 2: Small (One Block)')
voxelizer_small.forward(coords, center, atom_features, radii=1.0, out=grid_small)
draw_pse(f'{save_dir}/small.pse', ligand_rdmol, pocket_rdmol, ligand_grid_small, pocket_grid_small, \
        ligand_channels, pocket_channels, center, voxelizer_small.resolution)

print('Test 3: High Resolution')
voxelizer_hr.forward(coords, center, atom_features, radii=1.0, out=grid_hr)
draw_pse(f'{save_dir}/hr.pse', ligand_rdmol, pocket_rdmol, ligand_grid_hr, pocket_grid_hr, \
        ligand_channels, pocket_channels, center, voxelizer_hr.resolution)

print('Test 4: With Atom-wise Radii')
voxelizer.forward(coords, center, atom_features, atom_radii, out=grid)
draw_pse(f'{save_dir}/atom-wise.pse', ligand_rdmol, pocket_rdmol, ligand_grid, pocket_grid, \
        ligand_channels, pocket_channels, center, voxelizer.resolution)

print('Test 5: Channel-Wise Radii: True')
voxelizer.channel_wise_radii = True
voxelizer.forward(coords, center, atom_features, channel_radii, out=grid)
draw_pse(f'{save_dir}/channel-wise.pse', ligand_rdmol, pocket_rdmol, ligand_grid, pocket_grid, \
        ligand_channels, pocket_channels, center, voxelizer.resolution)
voxelizer.channel_wise_radii = False

print('Test 6: Binary: True')
voxelizer.density = 'binary'
voxelizer.forward(coords, center, atom_features, radii = 1.0, out=grid)
draw_pse(f'{save_dir}/binary.pse', ligand_rdmol, pocket_rdmol, ligand_grid, pocket_grid, \
        ligand_channels, pocket_channels, center, voxelizer.resolution)
voxelizer.density = 'gaussian'

print('Test 7: Random transform')
new_coords = transform.forward(coords, center)
voxelizer.forward(new_coords, center, atom_features, radii = 1.0, out=grid)
draw_pse(f'{save_dir}/transform.pse', ligand_rdmol, pocket_rdmol, ligand_grid, pocket_grid, \
        ligand_channels, pocket_channels, center, voxelizer.resolution, new_coords=new_coords)

