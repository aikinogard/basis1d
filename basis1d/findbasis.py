import copy
import numpy as np
import matplotlib.pyplot as plt
from basis1d.basislib import basis
from basis1d.grid import DensityGrid


class findbasis:

    """
        optimize uncontracted basis using even-tempered method
        and convert densities on grid
        to coefficients on 1d gaussian type basis.

        n_lib: list, each row is a density on grid, the length of
                each row can be different

        xg_lib: list, each row is a grid, the length of
                each row can be different

        atoms_x_lib: list, each row is a list of atom coordinates,
                the length of each row can be different

        atoms_Z_lib: list, list of atomic index of atoms in one chain,
                        if it is a single list, then all densities
                        use the same atoms_Z.
                        if it is not a single list, then treat it as
                        a lib


        basis_data = \
                    {1: [('s',
                            [(2., 0.06462908245839719),
                             (0.8, 0.4066825517248162),
                             (0.32, 0.5468171685012185)])]
                    }
        or
        basis_data = basis['minix']
    """

    def __init__(self, n_lib, xg_lib, atoms_x_lib, atoms_Z_lib, basis_data,
                 verbose=False):
        assert len(n_lib) == len(xg_lib) == len(atoms_x_lib)

        self.Nt = len(n_lib)
        self.densities = []
        if isinstance(atoms_Z_lib[0], list):
            assert len(n_lib) == len(atoms_Z_lib)
            for i in range(self.Nt):
                self.densities.append(
                    DensityGrid(xg_lib[i], n_lib[i], atoms_x_lib[i],
                                atoms_Z_lib[i], verbose))
            self.single_atoms_Z = False
        else:
            for i in range(self.Nt):
                self.densities.append(
                    DensityGrid(xg_lib[i], n_lib[i], atoms_x_lib[i],
                                atoms_Z_lib, verbose))
            self.single_atoms_Z = True
        self.atoms_x_lib = atoms_x_lib
        self.atoms_Z_lib = atoms_Z_lib
        self.verbose = verbose

        if isinstance(basis_data, str):
            try:
                # search in the basislib
                self.basis_data = basis[basis_data]
                self.basis_name = basis_data
                self.from_basislib = True
            except:
                self.basis_data = {}
                self.basis_name = basis_data
        elif isinstance(basis_data, dict):
            self.basis_data = basis_data
            self.basis_name = 'user-defined'

    def __getitem__(self, i):
        return self.densities.__getitem__(i)

    def __len__(self):
        return self.densities.__len__()

    def stoich(self, atoms_Z):
        from collections import Counter
        from basis1d.tools import symbol
        cnt = Counter()
        for Z in atoms_Z:
            cnt[Z] += 1
        keys = sorted(cnt.keys())
        s = []
        for key in keys:
            if cnt[key] == 1:
                s.append(symbol[key])
            else:
                s.append("%s%d" % (symbol[key], cnt[key]))
        return "".join(s)

    def fit_density(self):
        for i, density in enumerate(self.densities):
            if self.verbose:
                if i == 0:
                    print 'fitting density for #0',
                elif i == self.Nt - 1:
                    print '#%d' % i
                else:
                    print '#%d' % i,
            density.make_bfs(self.basis_data)
            density.compute_c()

    def get_error(self, T=None):
        if T is None:
            T = range(self.Nt)
        err_lib = np.empty(len(T))
        for i, idx in enumerate(T):
            err_lib[i] = self.densities[idx].get_error()
        return err_lib

    def get_nc_lib(self, T=None, compute=False):
        if T is None:
            T = range(self.Nt)
        nc_lib = []
        if compute:
            for i, idx in enumerate(T):
                if self.verbose:
                    if i == 0:
                        print 'fitting density for #0',
                    elif i == self.Nt - 1:
                        print '#%d' % i
                    else:
                        print '#%d' % i,
                self.densities[idx].make_bfs(self.basis_data)
                self.densities[idx].compute_c()
                nc_lib.append(self.densities[idx].c)
        else:
            for i, idx in enumerate(T):
                nc_lib.append(self.densities[idx].c)
        return np.array(nc_lib)

    def basis_tier(self, Z, primary_shell, write_over=False, showerr=False):
        if primary_shell not in self.basis_data[Z]:
            raise RuntimeError("primary shell should be in basis data")
        Nshell = len(self.basis_data[Z])
        unsort_basis = copy.deepcopy(self.basis_data[Z])
        unsort_basis.remove(primary_shell)
        sort_basis = [primary_shell]
        err_min_list = np.empty(Nshell)

        err = 0.
        for density in self:
            density.make_bfs({Z: sort_basis})
            density.compute_c()
            err += density.get_error()
        err = err / len(self)
        err_min_list[0] = err
        print 'primary shell is', primary_shell
        print 'MAE=%4.10f' % err_min_list[0]

        for i in range(Nshell - 1):
            print 'sorting shell...#%d' % (i + 1)
            err_min = np.inf
            shell_best = None
            print 'trying...shell',
            for j, shell in enumerate(unsort_basis):
                print '#%d' % j,
                sort_basis.append(shell)
                err = 0.
                for density in self:
                    density.make_bfs({Z: sort_basis})
                    density.compute_c()
                    err += density.get_error()
                err = err / len(self)
                sort_basis.remove(shell)
                if err < err_min:
                    shell_best = shell
                    err_min = err
            sort_basis.append(shell_best)
            unsort_basis.remove(shell_best)
            err_min_list[i + 1] = err_min
            print 'done!'
            print 'best shell is', shell_best
            print 'MAE=%4.10f' % err_min
        print "sorted basis / fitting error:"
        err_range = err_min_list[0] - err_min_list[-1]
        for (shell, err_min) in zip(sort_basis, err_min_list):
            print "%s / %4.10f / %4.10f%%" %\
                (shell, err_min, 100 *
                 (1 - (err_min - err_min_list[-1]) / err_range))
        if showerr:
            plt.plot(100 * (1 - (err_min_list - err_min_list[-1]) / err_range),
                     'ro--')
            plt.show()
        if write_over:
            self.basis_data[Z] = sort_basis
        return sort_basis

    def optimize_bf(self, Z, shell, alist, blist=1, Nn=1, kfold=10, doadd=True,
                    showerr=False):
        if Nn == 1:
            blist = [1]
            b_is_list = False
        else:
            b_is_list = True
        if sum([1 for b in blist if b >= 1]) > 0 and len(blist) != 1:
            raise ValueError('b should be smaller than 1')
        print 'optimize basis function with even-tempered method \
            with %d-fold cross validation' % kfold
        print 'add to basis data: %s' % doadd
        print 'atomic index: %d' % Z
        print 'shell: %s' % shell
        print 'list of a: %s' % alist
        print 'list of b: %s' % blist
        print 'number of new basis: %d\n' % Nn

        p = np.arange(self.Nt)
        if self.Nt % kfold:
            addin = kfold - self.Nt % kfold
            p = np.append(p, np.random.choice(self.Nt, addin))

        np.random.shuffle(p)
        p = np.reshape(p, (kfold, -1))

        err_min = np.empty(kfold)
        a_opt = np.empty(kfold)
        b_opt = np.empty(kfold)

        err_min[:] = np.inf

        for i, S in enumerate(p):
            for a in alist:
                for b in blist:
                    self.basis_data[Z].extend(
                        [(shell, [(a * b ** m, 1.)]) for m in range(Nn)])
                    err = 0.
                    for idx in S:
                        self.densities[idx].make_bfs(self.basis_data)
                        self.densities[idx].compute_c()
                        err += self.densities[idx].get_error()
                    err = err / len(S)

                    if err < err_min[i]:
                        err_min[i] = err
                        a_opt[i] = a
                        b_opt[i] = b
                    del self.basis_data[Z][-Nn:]
            print '\tvalidation set: %s' % S
            print '\toptimized a=%f\tb=%f' % (a_opt[i], b_opt[i])
            print '\texpn:%s\n' % [a_opt[i] * b_opt[i] ** m for m in range(Nn)]
        shell_data = [(shell, [(np.median(a_opt) * np.median(b_opt) ** m, 1.)])
                      for m in range(Nn)]
        print 'from cross validation:'
        print 'optimized a=%f\tb=%f' % (np.median(a_opt), np.median(b_opt))

        if np.median(a_opt) == min(alist):
            print '\toptimized a is the smallest value in alist'
        elif np.median(a_opt) == max(alist):
            print '\toptimized a is the largest value in alist'
        if b_is_list:
            if np.median(b_opt) == min(blist):
                print '\toptimized b is the smallest value in blist'
            elif np.median(b_opt) == max(blist):
                print '\toptimized b is the largest value in blist'

        print 'optimized new shell: %s' % shell_data

        self.add_shell(Z, shell_data)
        if showerr:
            # compute error
            self.fit_density()
            err = self.get_error()
            print 'MAE =', np.mean(err)
            print 'MAX =', np.amax(err)
            print 'MIN =', np.amin(err)
            plt.plot(err)
            plt.show()

        if doadd is False:
            # remove this shell
            del self.basis_data[Z][-Nn:]

        return shell_data

    def add_shell(self, Z, shell_data):
        "add new shell data into basis data"
        self.basis_data[Z].extend(shell_data)
        if self.from_basislib:
            self.from_basislib = False
            self.basis_name = 'user-defined'

    def remove_shell(self, Z, shell_data):
        "remove shell data from basis data"
        for shell in shell_data:
            self.basis_data[Z].remove(shell)

    def output(self, T=None, name=None, fobj=None, atoms_Z=None):
        "output density information to a .py file"
        dens_dict = {}
        if T is None:
            T = range(self.Nt)
        dens_dict['basis_name'] = self.basis_name
        dens_dict['basis_data'] = self.basis_data

        if self.single_atoms_Z:
            if name is None:
                name = '%sNt%d' %\
                    (self.stoich(self.atoms_Z_lib), self.Nt)

            dens_dict['name'] = name

            dens_dict['atoms_Z'] = self.atoms_Z_lib

            dens_dict['nc_lib'] = self.get_nc_lib(T)
            dens_dict['atoms_x_lib'] = np.array(self.atoms_x_lib)[T]

        else:
            if atoms_Z is None:
                raise RuntimeError('There are different chains, please\
                    specify atoms_Z')
            if name is None:
                name = '%sNt%d' %\
                    (self.stoich(atoms_Z), self.Nt)

            T_single = []
            atoms_x_lib_single = []
            for i in T:
                if self.atoms_Z_lib[i] == atoms_Z:
                    T_single.append(i)
                    atoms_x_lib_single.append(self.atoms_x_lib[i])

            dens_dict['name'] = name

            dens_dict['atoms_Z'] = atoms_Z

            dens_dict['nc_lib'] = self.get_nc_lib(T_single)
            dens_dict['atoms_x_lib'] = np.array(atoms_x_lib_single)

        if fobj:
            from basis1d.tools import dict2str
            record = ['import numpy as np', '%s=\\' %
                      name, dict2str(dens_dict)]
            fobj.write('\n'.join(record))
        else:
            return dens_dict
